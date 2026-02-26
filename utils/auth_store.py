# -*- coding: utf-8 -*-
"""
JSON-backed user store for authentication.

Replaces the SQLite `users` table with a plain JSON file at
`config/users.json`.  All writes are atomic (os.replace) and the
in-memory state is protected by a module-level threading.Lock so the
module is safe to use from FastAPI worker threads.

@TASK T-auth-store - JSON user store
@SPEC CLAUDE.md#Security
@TEST tests/utils/test_auth_store.py
"""

import json
import os
import re
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Absolute path to the JSON file regardless of cwd
_USERS_FILE: Path = Path(__file__).parent.parent / "config" / "users.json"

# Username must be 1-100 chars, alphanumeric plus _ and -
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

# Module-level lock protects every read/write cycle
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string (no microseconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _validate_username(username: str) -> bool:
    """Return True when *username* matches the allowed pattern."""
    return bool(_USERNAME_RE.match(username))


def _empty_store() -> dict:
    """Return a fresh, empty store structure."""
    return {"users": {}, "next_id": 1}


def _read_raw() -> dict:
    """
    Read and parse the JSON file, returning the raw store dict.

    Returns an empty store when the file does not exist or is unreadable.
    Does NOT acquire the lock — callers must hold it.
    """
    if not _USERS_FILE.exists():
        return _empty_store()
    try:
        with _USERS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Minimal schema validation
        if not isinstance(data.get("users"), dict):
            data["users"] = {}
        if not isinstance(data.get("next_id"), int):
            data["next_id"] = (
                max((u.get("id", 0) for u in data["users"].values()), default=0) + 1
            )
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return _empty_store()


def _write_raw(data: dict) -> bool:
    """
    Atomically write *data* to ``config/users.json``.

    Uses a sibling temp-file + ``os.replace`` so a crash during the write
    never leaves a partially-written file.  Does NOT acquire the lock —
    callers must hold it.

    Returns True on success, False on any I/O error.
    """
    try:
        _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)

        # Write to a temp file in the same directory so os.replace is atomic
        # even on Windows (same filesystem / same volume).
        fd, tmp_path = tempfile.mkstemp(
            dir=_USERS_FILE.parent,
            prefix=".users_tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_path, _USERS_FILE)
        except Exception:
            # Best-effort cleanup of the orphaned temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_users() -> dict:
    """
    Load all users from ``config/users.json``.

    Returns a dict keyed by username::

        {
            "admin": {
                "id": 1,
                "username": "admin",
                "password_hash": "$2b$12$...",
                "role": "admin",
                "created_at": "2026-02-26T00:00:00"
            }
        }

    Returns an empty dict when the file does not exist or cannot be parsed.
    """
    with _lock:
        return dict(_read_raw().get("users", {}))


def save_users(users: dict) -> bool:
    """
    Overwrite the users section in ``config/users.json``.

    The ``next_id`` counter is recomputed from the maximum existing id so
    that successive saves never reuse an id.

    Args:
        users: Mapping of username -> user-dict (as returned by
               :func:`load_users`).

    Returns:
        True on success, False on I/O failure.
    """
    with _lock:
        data = _read_raw()
        data["users"] = users
        # Recompute next_id to stay ahead of any existing id
        max_id = max((u.get("id", 0) for u in users.values()), default=0)
        data["next_id"] = max(data.get("next_id", 1), max_id + 1)
        return _write_raw(data)


def get_user(username: str) -> Optional[dict]:
    """
    Retrieve a single user dict by *username*.

    The returned dict contains all fields including ``password_hash``
    (callers performing authentication need the hash for verification).

    Returns None when the user does not exist or the file cannot be read.
    """
    if not _validate_username(username):
        return None
    with _lock:
        data = _read_raw()
        return data["users"].get(username)


def create_user(
    username: str,
    password_hash: str,
    role: str = "editor",
) -> Optional[dict]:
    """
    Create a new user entry.

    Auto-increments the ``id`` counter stored in ``next_id``.

    Args:
        username:      Must match ``^[a-zA-Z0-9_-]{1,100}$``.
        password_hash: Pre-hashed password (bcrypt recommended).
        role:          User role string, defaults to ``"editor"``.

    Returns:
        The new user dict on success, or None when the username already
        exists or the username is invalid.
    """
    if not _validate_username(username):
        return None

    with _lock:
        data = _read_raw()

        if username in data["users"]:
            # Duplicate — caller should handle this case
            return None

        new_id: int = data.get("next_id", 1)
        user: dict = {
            "id": new_id,
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "created_at": _now_iso(),
        }
        data["users"][username] = user
        data["next_id"] = new_id + 1

        if not _write_raw(data):
            return None

        # Return a copy so callers cannot mutate the stored dict
        return dict(user)


def update_user(username: str, updates: dict) -> bool:
    """
    Update mutable fields of an existing user.

    Only ``password_hash`` and ``role`` can be changed through this
    function.  Immutable fields (``id``, ``username``, ``created_at``)
    are silently ignored even if present in *updates*.

    Args:
        username: Target username.
        updates:  Dict with any subset of ``{"password_hash", "role"}``.

    Returns:
        True on success, False when the user does not exist or the write
        fails.
    """
    if not _validate_username(username):
        return False

    # Only these fields are mutable
    _MUTABLE = {"password_hash", "role"}
    safe_updates = {k: v for k, v in updates.items() if k in _MUTABLE}

    if not safe_updates:
        # Nothing to do — treat as success
        return True

    with _lock:
        data = _read_raw()

        if username not in data["users"]:
            return False

        data["users"][username].update(safe_updates)
        return _write_raw(data)


def delete_user(username: str) -> bool:
    """
    Delete a user by *username*.

    Args:
        username: Target username.

    Returns:
        True when the user was removed (or did not exist), False on I/O
        error.  Deleting a non-existent user is considered a success so
        that the operation is idempotent.
    """
    if not _validate_username(username):
        return False

    with _lock:
        data = _read_raw()

        if username not in data["users"]:
            # Already absent — idempotent success
            return True

        del data["users"][username]
        return _write_raw(data)


def get_all_users() -> list:
    """
    Return a list of all users with ``password_hash`` stripped.

    Suitable for returning through the admin API without leaking
    credential material.

    Returns:
        List of user dicts ordered by ``id`` ascending.  Each dict
        contains ``id``, ``username``, ``role``, ``created_at`` but
        NOT ``password_hash``.
    """
    with _lock:
        data = _read_raw()

    users = []
    for user in data["users"].values():
        safe = {k: v for k, v in user.items() if k != "password_hash"}
        users.append(safe)

    users.sort(key=lambda u: u.get("id", 0))
    return users
