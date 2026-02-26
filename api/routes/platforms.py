# -*- coding: utf-8 -*-
"""
Platforms Routes
Upload platform management endpoints
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from api.dependencies.auth import User, get_current_user, get_current_admin_user

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.config_manager import get_config_manager

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


# --- Pydantic Schemas ---

class AddPlatformRequest(BaseModel):
    """Add platform request"""
    platform_id: str = Field(..., min_length=1, description="Platform identifier")
    display_name: str = Field(..., min_length=1, description="Display name")
    title_column: int = Field(..., description="Title column index")
    content_column: int = Field(..., description="Content column index")
    completed_column: int = Field(..., description="Completed column index")
    credentials_section: Optional[str] = Field(None, description="Credentials config section name")


class UpdatePlatformRequest(BaseModel):
    """Update platform request (partial)"""
    display_name: Optional[str] = None
    title_column: Optional[int] = None
    content_column: Optional[int] = None
    completed_column: Optional[int] = None
    credentials_section: Optional[str] = None
    enabled: Optional[bool] = None


# --- Routes ---

@router.get("", status_code=status.HTTP_200_OK)
async def get_platforms(current_user: User = Depends(get_current_user)):
    """
    List all upload platforms

    Returns all configured upload platforms and their settings.
    """
    config_manager = get_config_manager()
    platforms = config_manager.get_all_platforms()
    enabled = config_manager.get_enabled_platforms()

    return {
        "platforms": platforms,
        "enabled": enabled
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_platform(
    request: AddPlatformRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Add a new upload platform (admin only)

    Adds platform configuration with column mappings.
    """
    config_manager = get_config_manager()

    # Check if platform already exists
    platforms = config_manager.get_all_platforms()
    if request.platform_id in platforms:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Platform '{request.platform_id}' already exists"
        )

    success = config_manager.add_platform(
        platform_id=request.platform_id,
        display_name=request.display_name,
        title_column=request.title_column,
        content_column=request.content_column,
        completed_column=request.completed_column,
        credentials_section=request.credentials_section
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add platform"
        )

    return {
        "message": f"Platform '{request.platform_id}' added successfully",
        "platform": config_manager.get_platform_config(request.platform_id)
    }


@router.put("/{platform_id}", status_code=status.HTTP_200_OK)
async def update_platform(
    platform_id: str,
    request: UpdatePlatformRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Update platform configuration (admin only)

    Updates specific fields of a platform's configuration.
    """
    config_manager = get_config_manager()

    # Check if platform exists
    platforms = config_manager.get_all_platforms()
    if platform_id not in platforms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform '{platform_id}' not found"
        )

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided"
        )

    success = config_manager.update_platform(platform_id, updates)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update platform"
        )

    return {
        "message": f"Platform '{platform_id}' updated successfully",
        "platform": config_manager.get_platform_config(platform_id)
    }


@router.delete("/{platform_id}", status_code=status.HTTP_200_OK)
async def remove_platform(
    platform_id: str,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Remove an upload platform (admin only)

    Permanently removes platform from configuration.
    """
    config_manager = get_config_manager()

    # Check if platform exists
    platforms = config_manager.get_all_platforms()
    if platform_id not in platforms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform '{platform_id}' not found"
        )

    config_manager.remove_platform(platform_id)

    return {"message": f"Platform '{platform_id}' removed successfully"}
