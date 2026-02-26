# -*- coding: utf-8 -*-
"""
Authentication Routes
Login and user management endpoints
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from api.schemas.auth import LoginRequest, LoginResponse, TokenResponse, UserResponse
from api.dependencies.auth import (
    authenticate_user, create_access_token, get_current_user, User,
    verify_password, _fetch_user_dict, check_rate_limit, record_login_attempt
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.auth_store import update_user as update_user_in_store
from utils.logger import audit_log

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# --- Pydantic Schemas ---

class ChangeMyPasswordRequest(BaseModel):
    """Change own password request"""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (minimum 6 characters)")


# --- Helper Functions ---

def _update_own_password(username: str, password_hash: str) -> bool:
    """Update user's own password via auth_store"""
    return update_user_in_store(username, {"password_hash": password_hash})


# --- Routes ---

@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, req: Request = None):
    """
    Login endpoint

    Authenticates user with username and password, returns JWT token.
    Default admin credentials: username=admin, password=admin (change on first login)

    Returns password_change_required=True if using default credentials.
    """
    # M2: Rate limiting
    client_ip = req.client.host if req and req.client else "unknown"
    await check_rate_limit(req)

    user = authenticate_user(request.username, request.password)

    if not user:
        record_login_attempt(client_ip)
        audit_log("login_failed", request.username, {"reason": "invalid_credentials"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.username)

    # Check for default password (admin/admin)
    password_change_required = (request.username == "admin" and request.password == "admin")

    # Audit log for successful login
    audit_log("login", user.username, {
        "password_change_required": password_change_required
    })

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role
        ),
        password_change_required=password_change_required
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint

    Client handles token removal. Server acknowledges the request.
    """
    audit_log("logout", current_user.username)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information

    Requires valid JWT token in Authorization header.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )


@router.put("/password", status_code=status.HTTP_200_OK)
async def change_my_password(
    request: ChangeMyPasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Change current user's password

    Verifies current password, then updates to new password with bcrypt hash.
    """
    # Verify current password
    user_data = await asyncio.to_thread(_fetch_user_dict, current_user.username)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not verify_password(request.current_password, user_data['password_hash']):
        audit_log("password_change_failed", current_user.username, {"reason": "incorrect_current_password"})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Hash new password with bcrypt
    new_hash = bcrypt.hashpw(
        request.new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    try:
        updated = await asyncio.to_thread(_update_own_password, current_user.username, new_hash)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        audit_log("password_change", current_user.username)
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update password: {str(e)}"
        )
