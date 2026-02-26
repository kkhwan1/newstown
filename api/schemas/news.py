# -*- coding: utf-8 -*-
"""
News Schemas
News list and stats models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class NewsItem(BaseModel):
    """Single news item"""
    id: int = Field(..., description="News ID")
    title: str = Field(..., description="News title")
    content: Optional[str] = Field(None, description="News content")
    link: Optional[str] = Field(None, description="News link")
    category: Optional[str] = Field(None, description="News category")
    status: str = Field(..., description="News status (pending/uploaded/failed)")
    created_at: Optional[datetime] = Field(None, description="Creation time")
    uploaded_at: Optional[datetime] = Field(None, description="Upload time")

    class Config:
        from_attributes = True


class NewsListResponse(BaseModel):
    """News list response"""
    news: List[NewsItem] = Field(default_factory=list, description="List of news items")
    total: int = Field(..., description="Total news count")
    limit: int = Field(..., description="Page limit")
    offset: int = Field(..., description="Page offset")


class NewsStatsResponse(BaseModel):
    """News statistics response"""
    total: int = Field(..., description="Total news count")
    pending: int = Field(..., description="Pending news count")
    uploaded: int = Field(..., description="Uploaded news count")
    failed: int = Field(..., description="Failed news count")
    by_category: List[Dict[str, Any]] = Field(default_factory=list, description="Category-wise counts")
