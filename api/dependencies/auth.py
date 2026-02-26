# -*- coding: utf-8 -*-
"""
Authentication Dependencies
JWT token validation and user extraction

@TASK P0-T0.sqlite-auth-fix - SQLite/PostgreSQL 호환 인증 구현
@SPEC docs/planning/02-trd.md#authentication
"""
import os
import hmac
import hashlib
import secrets
import time as _time
import bcrypt
from typing import Optional, List
from collections import defaultdict
from fastapi import Depends, HTTPException, status, Query, WebSocket, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

import logging

from utils.auth_store import get_user as _get_user_from_store, update_user as _update_user_in_store

logger = logging.getLogger(__name__)

# JWT Secret from environment
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("JWT_SECRET_KEY must be set in production environment")
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("JWT_SECRET_KEY is not set! Generated temporary key. Set JWT_SECRET_KEY in .env for persistent sessions.")
JWT_ALGORITHM = "HS256"

# --- Rate Limiting ---
_login_attempts: dict = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60


def check_login_rate_limit(identifier: str) -> bool:
    """Check if login is rate-limited. Returns True if allowed, False if blocked."""
    now = _time.time()
    _login_attempts[identifier] = [t for t in _login_attempts[identifier] if now - t < LOGIN_LOCKOUT_SECONDS]
    if not _login_attempts[identifier]:
        del _login_attempts[identifier]
        return True
    return len(_login_attempts[identifier]) < LOGIN_MAX_ATTEMPTS


def record_login_attempt(identifier: str):
    """Record a failed login attempt."""
    _login_attempts[identifier].append(_time.time())


async def check_rate_limit(request: Request):
    """Rate limit dependency for login endpoint"""
    client_ip = request.client.host if request.client else "unknown"
    if not check_login_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again after {LOGIN_LOCKOUT_SECONDS} seconds."
        )

security = HTTPBearer()


class User(BaseModel):
    """User model"""
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _is_legacy_sha256_hash(hashed_password: str) -> bool:
    """Check if the stored hash is a legacy SHA256 hex digest (not bcrypt)"""
    return not (hashed_password.startswith('$2') and '$' in hashed_password[4:])


def _migrate_password_hash(username: str, new_hash: str):
    """Migrate a user's password hash from SHA256 to bcrypt"""
    try:
        if _update_user_in_store(username, {"password_hash": new_hash}):
            logger.info("Auto-migrated password hash to bcrypt for user '%s'", username)
        else:
            logger.warning("Failed to auto-migrate password hash for user '%s': user not found", username)
    except Exception as e:
        logger.warning("Failed to auto-migrate password hash for user '%s': %s", username, e)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    try:
        # Check if hash is bcrypt format (starts with $2a$ or $2b$)
        if not _is_legacy_sha256_hash(hashed_password):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        else:
            # Legacy SHA256 hash support for migration
            sha256_hash = hashlib.sha256(plain_password.encode()).hexdigest()
            return hmac.compare_digest(sha256_hash, hashed_password)
    except Exception:
        return False


def _fetch_user_dict(username: str) -> Optional[dict]:
    """Get user data as dictionary from JSON user store"""
    try:
        return _get_user_from_store(username)
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Get user from database by username"""
    user_data = _fetch_user_dict(username)

    if user_data:
        return User(
            id=user_data['id'],
            username=user_data['username'],
            role=user_data['role']
        )
    return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user_data = _fetch_user_dict(username)

    if user_data and verify_password(password, user_data['password_hash']):
        # Auto-migrate legacy SHA256 hash to bcrypt on successful login
        if _is_legacy_sha256_hash(user_data['password_hash']):
            try:
                new_hash = hash_password(password)
                _migrate_password_hash(user_data['username'], new_hash)
            except Exception:
                pass  # Migration failure is non-blocking

        return User(
            id=user_data['id'],
            username=user_data['username'],
            role=user_data['role']
        )
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Simple token validation (username is encoded in token)
        # For production, use proper JWT library like python-jose
        token = credentials.credentials

        # Token format: "username:timestamp:expiry:signature" (new)
        # Legacy format: "username:timestamp:signature" (old, accepted with warning)
        parts = token.split(':')

        if len(parts) == 4:
            # New format with expiry
            username, timestamp, expiry, signature = parts

            # Verify signature (covers username:timestamp:expiry)
            expected_signature = hmac.new(
                JWT_SECRET_KEY.encode(),
                f"{username}:{timestamp}:{expiry}".encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                raise credentials_exception

            # Check expiration
            try:
                if int(_time.time()) > int(expiry):
                    raise credentials_exception
            except (ValueError, TypeError):
                raise credentials_exception

        elif len(parts) == 3:
            # Legacy format without expiry (backward compatibility)
            username, timestamp, signature = parts
            logger.warning("Legacy 3-part token used by user '%s'. Tokens without expiry are deprecated.", username)

            expected_signature = hmac.new(
                JWT_SECRET_KEY.encode(),
                f"{username}:{timestamp}".encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                raise credentials_exception

            # M1: Apply 24-hour expiry to legacy tokens
            try:
                if int(_time.time()) - int(timestamp) > 86400:
                    raise credentials_exception
            except (ValueError, TypeError):
                raise credentials_exception
        else:
            raise credentials_exception

        # Get user from database
        user = get_user_by_username(username)
        if user is None:
            raise credentials_exception

        return user

    except HTTPException:
        raise
    except Exception:
        raise credentials_exception


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current authenticated user (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = None
) -> Optional[User]:
    """
    Get current authenticated user from WebSocket connection

    Validates JWT token from query parameter for WebSocket authentication.
    Returns None if authentication fails (allows graceful disconnect).
    """
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return None

    try:
        # Token format: "username:timestamp:expiry:signature" (new)
        # Legacy format: "username:timestamp:signature" (old, accepted with warning)
        parts = token.split(':')

        if len(parts) == 4:
            # New format with expiry
            username, timestamp, expiry, signature = parts

            expected_signature = hmac.new(
                JWT_SECRET_KEY.encode(),
                f"{username}:{timestamp}:{expiry}".encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                await websocket.close(code=1008, reason="Invalid token signature")
                return None

            # Check expiration
            try:
                if int(_time.time()) > int(expiry):
                    await websocket.close(code=1008, reason="Token expired")
                    return None
            except (ValueError, TypeError):
                await websocket.close(code=1008, reason="Invalid token expiry")
                return None

        elif len(parts) == 3:
            # Legacy format without expiry (backward compatibility)
            username, timestamp, signature = parts
            logger.warning("Legacy 3-part WebSocket token used by user '%s'. Tokens without expiry are deprecated.", username)

            expected_signature = hmac.new(
                JWT_SECRET_KEY.encode(),
                f"{username}:{timestamp}".encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                await websocket.close(code=1008, reason="Invalid token signature")
                return None

            # M1: Apply 24-hour expiry to legacy tokens
            try:
                if int(_time.time()) - int(timestamp) > 86400:
                    await websocket.close(code=1008, reason="Token expired")
                    return None
            except (ValueError, TypeError):
                await websocket.close(code=1008, reason="Invalid token timestamp")
                return None
        else:
            await websocket.close(code=1008, reason="Invalid token format")
            return None

        # Get user from database
        user = get_user_by_username(username)
        if user is None:
            await websocket.close(code=1008, reason="User not found")
            return None

        return user

    except Exception as e:
        logger.error("WebSocket authentication failed: %s", e)
        await websocket.close(code=1008, reason="Authentication failed")
        return None


def create_access_token(username: str, expires_in: int = 86400) -> str:
    """Create access token for user with expiration

    Args:
        username: Username to encode in token
        expires_in: Token lifetime in seconds (default: 86400 = 24 hours)

    Returns:
        Token string in format 'username:timestamp:expiry:signature'
    """
    timestamp = int(_time.time())
    expiry = timestamp + expires_in
    message = f"{username}:{timestamp}:{expiry}"
    signature = hmac.new(
        JWT_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{username}:{timestamp}:{expiry}:{signature}"
