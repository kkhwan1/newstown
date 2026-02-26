# -*- coding: utf-8 -*-
"""
Sync Routes (Sheet-only)
Google Sheets status and management endpoints

After DB removal, sync routes only interact with Google Sheets.
"""
import sys
import asyncio
from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.dependencies.auth import User, get_current_user, get_current_admin_user
from utils.config_manager import get_config_manager
from utils.sheet_client import delete_sheet_rows, count_sheet_news

router = APIRouter(prefix="/api/sync", tags=["sync"])


# =============================================================================
# Response Models
# =============================================================================

class SyncStatusResponse(BaseModel):
    """Sync status response (sheet-only)"""
    sheet_count: int
    message: str = ""


class SheetCountResponse(BaseModel):
    """Sheet row count response"""
    count: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=SyncStatusResponse, status_code=status.HTTP_200_OK)
async def get_sync_status(current_user: User = Depends(get_current_user)):
    """
    Get sheet status

    Returns the row count from Google Sheets.
    """
    cm = get_config_manager()
    sheet_url = cm.get("google_sheet", "url")

    if not sheet_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheets URL not configured"
        )

    try:
        stats = await asyncio.to_thread(count_sheet_news, sheet_url)
        sheet_count = stats["total"]
    except HTTPException:
        raise
    except Exception:
        sheet_count = 0

    return SyncStatusResponse(
        sheet_count=sheet_count,
        message=f"Google Sheet contains {sheet_count} rows (excluding header)"
    )


@router.get("/sheet-count", status_code=status.HTTP_200_OK)
async def get_sheet_count(current_user: User = Depends(get_current_user)):
    """Get total row count from Google Sheet"""
    cm = get_config_manager()
    sheet_url = cm.get("google_sheet", "url")

    if not sheet_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheets URL not configured"
        )

    try:
        stats = await asyncio.to_thread(count_sheet_news, sheet_url)
        return {"count": stats["total"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sheet count"
        )


@router.delete("/delete-from-sheet", status_code=status.HTTP_200_OK)
async def delete_from_sheet(
    row_numbers: List[int] = Query(..., description="Row numbers to delete from sheet"),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete rows from Google Sheet

    Deletes specified rows from Google Sheets by row number.
    Requires admin role. Row numbers must be >= 2 (row 1 is header), max 1000 rows per request.
    """
    if any(r < 2 for r in row_numbers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All row numbers must be >= 2 (row 1 is header)"
        )

    if len(row_numbers) > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot delete more than 1000 rows at once"
        )

    cm = get_config_manager()
    sheet_url = cm.get("google_sheet", "url")

    if not sheet_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheets URL not configured"
        )

    try:
        deleted = await asyncio.to_thread(delete_sheet_rows, sheet_url, row_numbers)

        return {
            "success": True,
            "message": f"Deleted {deleted} rows from sheet",
            "deleted_count": deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete from sheet failed"
        )
