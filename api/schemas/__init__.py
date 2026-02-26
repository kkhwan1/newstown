# -*- coding: utf-8 -*-
"""
API Schemas
Pydantic models for request/response validation
"""
from .auth import LoginRequest, TokenResponse, UserResponse
from .config import ConfigResponse, ConfigUpdate
from .process import ProcessStatusResponse, ProcessActionRequest, ProcessListResponse
from .news import NewsListResponse, NewsItem, NewsStatsResponse

__all__ = [
    'LoginRequest',
    'TokenResponse',
    'UserResponse',
    'ConfigResponse',
    'ConfigUpdate',
    'ProcessStatusResponse',
    'ProcessActionRequest',
    'ProcessListResponse',
    'NewsListResponse',
    'NewsItem',
    'NewsStatsResponse',
]
