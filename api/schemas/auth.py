# -*- coding: utf-8 -*-
"""
Authentication Schemas
Login request and token response models
"""
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """Login request schema"""
    username: str = Field(..., min_length=1, max_length=100, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: 'UserResponse' = Field(..., description="User information")


class LoginResponse(TokenResponse):
    """Login response with optional password change warning"""
    password_change_required: bool = Field(
        default=False,
        description="True if user is using default credentials and should change password"
    )


class UserResponse(BaseModel):
    """User information response"""
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="User role (admin/user)")

    class Config:
        from_attributes = True
