import os
import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional, List, Dict

LOG_FILE = Path(__file__).parent.parent / "logs" / "activity.log"
MAX_LINES = 500

_lock = Lock()

def ensure_log_dir():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def add_log(message: str, level: str = "INFO", category: str = "SYSTEM"):
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "category": category,
        "message": message
    }

    with _lock:
        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []

            lines.append(json.dumps(log_entry, ensure_ascii=False) + chr(10))

            if len(lines) > MAX_LINES:
                lines = lines[-MAX_LINES:]

            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Log error: {e}")

def get_logs(limit: int = 100, category: Optional[str] = None) -> List[Dict]:
    ensure_log_dir()
    logs = []

    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in reversed(lines):
                try:
                    entry = json.loads(line.strip())
                    if category is None or entry.get('category') == category:
                        logs.append(entry)
                    if len(logs) >= limit:
                        break
                except Exception as e:
                    print(f"Log parse error: {e}")
                    continue
    except Exception as e:
        print(f"Read log error: {e}")

    return logs

def clear_logs():
    ensure_log_dir()
    with _lock:
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("")
        except Exception as e:
            print(f"Warning: 로그 삭제 실패: {e}")


# --- Audit Logger (M5) ---

_audit_logger = None

def _get_audit_logger():
    """Get or initialize the dedicated audit logger.

    Uses Python's logging module with a separate file handler
    writing to logs/audit.log in JSON format.
    """
    global _audit_logger
    if _audit_logger is None:
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        _audit_logger = logging.getLogger("audit")
        _audit_logger.setLevel(logging.INFO)
        _audit_logger.propagate = False

        if not _audit_logger.handlers:
            handler = logging.FileHandler(
                str(log_dir / "audit.log"),
                encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter('%(message)s'))
            _audit_logger.addHandler(handler)

    return _audit_logger


def audit_log(action: str, user: str, details: dict = None):
    """Write an audit log entry in JSON format to logs/audit.log.

    Args:
        action: Action performed (e.g., 'login', 'login_failed',
                'logout', 'password_change', 'process_start',
                'process_stop', 'config_change')
        user: Username who performed the action
        details: Additional details dict (optional)
    """
    logger = _get_audit_logger()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "user": user,
        "details": details or {}
    }
    logger.info(json.dumps(entry, ensure_ascii=False))
