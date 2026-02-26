# -*- coding: utf-8 -*-
"""
Admin Routes
User management endpoints (admin only)
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import bcrypt

from api.dependencies.auth import User, get_current_admin_user
from utils.logger import audit_log

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.auth_store import (
    get_all_users as store_get_all_users,
    create_user as store_create_user,
    delete_user as store_delete_user,
    update_user as store_update_user,
    get_user as store_get_user,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Pydantic Schemas ---

class CreateUserRequest(BaseModel):
    """Create user request"""
    username: str = Field(..., min_length=1, max_length=100, description="Username")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")
    role: str = Field(default="user", description="User role (admin/user)")


class ChangePasswordRequest(BaseModel):
    """Change user password request (admin)"""
    new_password: str = Field(..., min_length=6, description="New password (minimum 6 characters)")


class ChangeRoleRequest(BaseModel):
    """Change user role request"""
    role: str = Field(..., description="New role (admin/user)")


# --- Helper Functions ---

def _hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _get_all_users() -> Dict[str, Dict[str, Any]]:
    """Get all users from auth_store, returning a dict keyed by username"""
    user_list = store_get_all_users()
    users = {}
    for user in user_list:
        created_at = user.get('created_at')
        if created_at is not None:
            created_at = str(created_at)
        users[user['username']] = {
            "id": user['id'],
            "role": user['role'],
            "created_at": created_at
        }
    return users


def _create_user(username: str, password_hash: str, role: str) -> bool:
    """Create a new user via auth_store. Returns True on success, False on duplicate."""
    result = store_create_user(username, password_hash, role)
    return result is not None


def _user_exists(username: str) -> bool:
    """Check if user exists via auth_store"""
    return store_get_user(username) is not None


def _delete_user(username: str) -> bool:
    """Delete user via auth_store. Returns True only when the user actually existed."""
    if store_get_user(username) is None:
        return False
    return store_delete_user(username)


def _update_user_role(username: str, role: str) -> bool:
    """Update user role via auth_store"""
    if store_get_user(username) is None:
        return False
    return store_update_user(username, {"role": role})


def _update_user_password(username: str, password_hash: str) -> bool:
    """Update user password via auth_store"""
    if store_get_user(username) is None:
        return False
    return store_update_user(username, {"password_hash": password_hash})


# --- Routes ---

@router.get("/users", status_code=status.HTTP_200_OK)
async def get_users(current_user: User = Depends(get_current_admin_user)):
    """
    List all users (admin only)

    Returns dict of {username: {id, role, created_at}}.
    """
    users = await asyncio.to_thread(_get_all_users)
    return users


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Create a new user (admin only)

    Creates a user with bcrypt-hashed password.
    """
    # Check if user already exists
    exists = await asyncio.to_thread(_user_exists, request.username)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{request.username}' already exists"
        )

    # Validate role
    if request.role not in ('admin', 'user'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'user'"
        )

    password_hash = _hash_password(request.password)

    try:
        await asyncio.to_thread(_create_user, request.username, password_hash, request.role)
        audit_log("user_created", current_user.username, {"target_user": request.username, "role": request.role})
        return {"message": f"User '{request.username}' created successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.delete("/users/{username}", status_code=status.HTTP_200_OK)
async def delete_user(
    username: str,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete a user (admin only)

    Cannot delete yourself.
    """
    # Cannot delete self
    if username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    try:
        deleted = await asyncio.to_thread(_delete_user, username)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        audit_log("user_deleted", current_user.username, {"target_user": username})
        return {"message": f"User '{username}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.put("/users/{username}/role", status_code=status.HTTP_200_OK)
async def change_user_role(
    username: str,
    request: ChangeRoleRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Change user role (admin only)
    """
    # Validate role
    if request.role not in ('admin', 'user'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'user'"
        )

    try:
        updated = await asyncio.to_thread(_update_user_role, username, request.role)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        audit_log("role_changed", current_user.username, {"target_user": username, "new_role": request.role})
        return {"message": f"User '{username}' role updated to '{request.role}'"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update role: {str(e)}"
        )


@router.put("/users/{username}/password", status_code=status.HTTP_200_OK)
async def change_user_password(
    username: str,
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Change user password (admin only)

    Admin can change any user's password.
    """
    password_hash = _hash_password(request.new_password)

    try:
        updated = await asyncio.to_thread(_update_user_password, username, password_hash)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        audit_log("password_reset", current_user.username, {"target_user": username})
        return {"message": f"Password updated for user '{username}'"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update password: {str(e)}"
        )
