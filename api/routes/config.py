# -*- coding: utf-8 -*-
"""
Configuration Routes
Configuration management endpoints
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from api.schemas.config import ConfigResponse, ConfigUpdate
from api.dependencies.auth import User, get_current_user, get_current_admin_user
from utils.logger import audit_log

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.config_manager import get_config_manager

router = APIRouter(prefix="/api/config", tags=["configuration"])

SENSITIVE_SECTIONS = {'naver_api', 'golftimes', 'news_collection'}
SENSITIVE_KEYS = {'client_id', 'client_secret', 'site_pw', 'naver_client_id', 'naver_client_secret'}


def _mask_sensitive_fields(data: dict) -> dict:
    """Mask sensitive credentials in config data"""
    if not isinstance(data, dict):
        return data
    masked = dict(data)
    for key, value in masked.items():
        if key in SENSITIVE_KEYS and value:
            masked[key] = '***MASKED***'
    return masked


@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_config(current_user: User = Depends(get_current_user)):
    """
    Get full configuration

    Returns all configuration sections. Requires authentication.
    Sensitive credentials (passwords) are masked.
    """
    config_manager = get_config_manager()
    config = config_manager.get_all()

    # Mask sensitive fields in all sections
    for section_name in SENSITIVE_SECTIONS:
        if section_name in config and isinstance(config[section_name], dict):
            config[section_name] = _mask_sensitive_fields(config[section_name])

    return config


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def update_config(
    request: ConfigUpdate,
    current_user: User = Depends(get_current_admin_user)  # Admin only
):
    """
    Update configuration section

    Updates a specific configuration section with validation.
    Admin privileges required.
    """
    config_manager = get_config_manager()
    section = request.section
    data = request.data

    # Validate section with Pydantic if available
    if hasattr(config_manager, 'set_section_with_validation'):
        success, error_msg = config_manager.set_section_with_validation(section, data, save=True)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {error_msg}"
            )
    else:
        config_manager.set_section(section, data, save=True)

    # Return updated section
    updated_data = config_manager.get(section)
    audit_log("config_updated", current_user.username, {"section": section})
    return {"section": section, "data": updated_data}


@router.get("/news", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_news_config(current_user: User = Depends(get_current_user)):
    """
    Get news collection configuration

    Returns configuration specifically for news collection.
    """
    config_manager = get_config_manager()
    data = config_manager.get_news_config()
    return _mask_sensitive_fields(data)


@router.get("/upload", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_upload_config(current_user: User = Depends(get_current_user)):
    """
    Get upload monitor configuration

    Returns configuration specifically for upload monitoring.
    """
    config_manager = get_config_manager()
    return config_manager.get_upload_config()


@router.get("/platforms", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_platforms_config(current_user: User = Depends(get_current_user)):
    """
    Get all upload platforms configuration

    Returns all available upload platforms and their settings.
    """
    config_manager = get_config_manager()
    platforms = config_manager.get_all_platforms()
    enabled = config_manager.get_enabled_platforms()

    return {
        "platforms": platforms,
        "enabled": enabled
    }


@router.get("/{section}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_config_section(
    section: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific configuration section

    Returns data for the requested configuration section.
    """
    config_manager = get_config_manager()
    data = config_manager.get(section)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration section '{section}' not found"
        )
    # Mask sensitive fields if this is a sensitive section
    if section in SENSITIVE_SECTIONS and isinstance(data, dict):
        data = _mask_sensitive_fields(data)
    return data


@router.put("/{section}/{key}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def update_config_key(
    section: str,
    key: str,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_admin_user)
):
    """
    Update a single configuration key within a section

    Updates a specific key in a configuration section.
    Admin privileges required.
    """
    config_manager = get_config_manager()
    value = request.get("value")
    config_manager.set(section, key, value, save=True)
    updated_data = config_manager.get(section)
    audit_log("config_key_updated", current_user.username, {"section": section, "key": key})
    return {"section": section, "data": updated_data}


@router.put("/{section}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def update_config_section(
    section: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_admin_user)
):
    """
    Update an entire configuration section

    Replaces all data in a configuration section.
    Admin privileges required.
    """
    config_manager = get_config_manager()

    if hasattr(config_manager, 'set_section_with_validation'):
        success, error_msg = config_manager.set_section_with_validation(section, data, save=True)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {error_msg}"
            )
    else:
        config_manager.set_section(section, data, save=True)

    updated_data = config_manager.get(section)
    audit_log("config_section_updated", current_user.username, {"section": section})
    return {"section": section, "data": updated_data}


@router.post("/naver-api/file", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def save_naver_api_to_file(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_admin_user)
):
    """
    Save Naver API credentials directly to config/naver_api.json file

    This endpoint saves the Naver API credentials to the JSON file
    so they are immediately available for news collection scripts.
    Admin privileges required.
    """
    import json

    client_id = request.get("client_id", "").strip()
    client_secret = request.get("client_secret", "").strip()

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client ID and Client Secret are required"
        )

    # Ensure config directory exists
    config_dir = Path(__file__).parent.parent.parent / "config"
    config_dir.mkdir(exist_ok=True)

    # Write to naver_api.json file
    naver_api_file = config_dir / "naver_api.json"
    with open(naver_api_file, 'w', encoding='utf-8') as f:
        json.dump({
            "naver_client_id": client_id,
            "naver_client_secret": client_secret
        }, f, indent=2, ensure_ascii=False)

    # Also save to config manager (JSON)
    config_manager = get_config_manager()
    config_manager.set("naver_api", "client_id", client_id, save=True)
    config_manager.set("naver_api", "client_secret", client_secret, save=True)

    audit_log("naver_api_saved", current_user.username, {"to_file": True})
    return {
        "success": True,
        "message": "Naver API credentials saved"
    }
