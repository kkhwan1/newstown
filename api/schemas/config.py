# -*- coding: utf-8 -*-
"""
Configuration Schemas
Config request and response models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ConfigResponse(BaseModel):
    """Full configuration response"""
    news_collection: Dict[str, Any] = Field(default_factory=dict, description="News collection settings")
    category_keywords: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict, description="Category keywords")
    upload_monitor: Dict[str, Any] = Field(default_factory=dict, description="Upload monitor settings")
    row_deletion: Dict[str, Any] = Field(default_factory=dict, description="Row deletion settings")
    google_sheet: Dict[str, str] = Field(default_factory=dict, description="Google Sheet settings")
    naver_api: Dict[str, str] = Field(default_factory=dict, description="Naver API settings")
    news_schedule: Dict[str, Any] = Field(default_factory=dict, description="News schedule settings")
    golftimes: Dict[str, str] = Field(default_factory=dict, description="GolfTimes credentials")
    upload_platforms: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Upload platforms")


class ConfigUpdate(BaseModel):
    """Configuration update request (partial update)"""
    section: str = Field(..., description="Configuration section name")
    data: Dict[str, Any] = Field(..., description="Configuration data to update")
