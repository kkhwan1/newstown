# -*- coding: utf-8 -*-
"""
Usage Routes
API usage statistics endpoint
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from api.dependencies.auth import User, get_current_user

router = APIRouter(prefix="/api/usage", tags=["usage"])

# Path to api_usage.json
USAGE_FILE = Path(__file__).parent.parent.parent / "config" / "api_usage.json"
DAILY_LIMIT = 25000  # Naver API daily limit


@router.get("/api", status_code=status.HTTP_200_OK)
async def get_api_usage(current_user: User = Depends(get_current_user)):
    """
    Get API usage statistics

    Returns contents of config/api_usage.json.
    """
    def _read_usage_file():
        if not USAGE_FILE.exists():
            return {"date": None, "calls": 0, "news_count": 0,
                    "daily_limit": DAILY_LIMIT, "remaining": DAILY_LIMIT, "usage_percent": 0}
        with open(USAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        calls = data.get("calls", 0)
        data["daily_limit"] = DAILY_LIMIT
        data["remaining"] = max(0, DAILY_LIMIT - calls)
        data["usage_percent"] = round((calls / DAILY_LIMIT) * 100, 1) if DAILY_LIMIT > 0 else 0
        return data

    try:
        return await asyncio.to_thread(_read_usage_file)
    except json.JSONDecodeError:
        return {"date": None, "calls": 0, "news_count": 0,
                "daily_limit": DAILY_LIMIT, "remaining": DAILY_LIMIT, "usage_percent": 0}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read API usage data: {str(e)}"
        )
