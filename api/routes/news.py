# -*- coding: utf-8 -*-
"""
News Routes
News management endpoints backed by Google Sheets.

@TASK T8 - DB 의존성 제거, Google Sheet 직접 연동
@SPEC CLAUDE.md#Architecture
"""
import asyncio
import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Depends, HTTPException, Path as FastPath, status, Query
from pydantic import BaseModel, Field

from api.schemas.news import NewsListResponse, NewsItem, NewsStatsResponse
from api.dependencies.auth import User, get_current_user, get_current_admin_user
from utils import sheet_client
from utils.config_manager import get_config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])


# ---------------------------------------------------------------------------
# Pydantic request schemas (unchanged from original)
# ---------------------------------------------------------------------------

class NewsSearchRequest(BaseModel):
    """News search request"""
    keyword: str = Field(..., min_length=1, description="Search keyword")
    display: int = Field(default=20, ge=1, le=100, description="Number of results")
    sort: Literal["date", "sim"] = Field(default="date", description="Sort order (date/sim)")


class NewsSaveItem(BaseModel):
    """Single news item to save"""
    title: str = Field(..., min_length=1)
    content: Optional[str] = None
    link: str = Field(..., min_length=1)
    category: Optional[str] = None
    search_keyword: Optional[str] = None


class NewsSaveRequest(BaseModel):
    """Save news items request"""
    news_list: List[NewsSaveItem] = Field(..., description="List of news items to save")
    category: Optional[str] = Field(None, description="Default category for all items")
    search_keyword: Optional[str] = Field(None, description="Search keyword used")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_sheet_url() -> str:
    """
    Return the configured Google Sheet URL.

    Raises HTTPException 400 when the URL is not set.
    """
    url = get_config_manager().get("google_sheet", "url") or ""
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheet URL not configured",
        )
    return url


def _sheet_row_to_news_item(row: Dict[str, Any]) -> NewsItem:
    """
    Convert a sheet_client row dict to a NewsItem.

    Field mapping:
        id          <- row_number (sheet row index, 1-based)
        title       <- title
        content     <- content (raw) or ai_content if raw is empty
        link        <- link
        category    <- category
        status      <- 'uploaded' when ai_title present, else 'pending'
        created_at  <- None (not tracked in sheet)
        uploaded_at <- None (not tracked in sheet)
    """
    has_ai = bool(row.get("ai_title") or row.get("ai_content"))
    return NewsItem(
        id=row["row_number"],
        title=row.get("title", ""),
        content=row.get("content") or row.get("ai_content") or None,
        link=row.get("link") or None,
        category=row.get("category") or None,
        status="uploaded" if has_ai else "pending",
        created_at=None,
        uploaded_at=None,
    )


def _search_naver_news(keyword: str, display: int = 20, sort: str = "date") -> Dict[str, Any]:
    """Search Naver news API (unchanged from original)."""
    import requests as req

    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise ValueError(
            "NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables are required"
        )

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": keyword, "display": display, "sort": sort}

    response = req.get(
        "https://openapi.naver.com/v1/search/news.json",
        headers=headers,
        params=params,
        timeout=10,
    )

    if response.status_code != 200:
        raise ValueError(
            f"Naver API returned status {response.status_code}: {response.text}"
        )

    data = response.json()

    # Strip HTML tags from titles and descriptions
    for item in data.get("items", []):
        item["title"] = re.sub(r"<[^>]+>", "", item.get("title", ""))
        item["description"] = re.sub(r"<[^>]+>", "", item.get("description", ""))

    return data


def _append_news_to_sheet(
    sheet_url: str,
    items: List[Dict[str, Any]],
    default_category: Optional[str],
) -> Dict[str, int]:
    """
    Append news items to the sheet, deduplicating by link.

    Returns dict with 'saved' and 'skipped' counts.
    """
    existing_links = sheet_client.get_existing_links(sheet_url)

    rows_to_append: List[List[Any]] = []
    skipped = 0

    for item in items:
        title = item.get("title", "").strip()
        content = (item.get("content") or item.get("description") or "").strip()
        link = item.get("link", "").strip()
        category = (item.get("category") or default_category or "").strip()

        if not title or not link:
            skipped += 1
            continue

        if link in existing_links:
            skipped += 1
            continue

        rows_to_append.append([title, content, link, category])
        existing_links.add(link)  # prevent duplicate within this batch

    saved = sheet_client.append_news_rows(sheet_url, rows_to_append)
    return {"saved": saved, "skipped": skipped}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=NewsListResponse, status_code=status.HTTP_200_OK)
async def get_news(
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status (pending/uploaded)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
):
    """
    Get news list from Google Sheet.

    Returns paginated news articles with optional category filtering.
    The 'status' filter (pending/uploaded) is applied after sheet data
    is retrieved — 'uploaded' means the row already has an AI-generated
    title in column E.
    """
    sheet_url = _get_sheet_url()

    try:
        # Fetch a larger window to support status_filter post-processing.
        # When status_filter is set we fetch all and filter in memory;
        # otherwise we use sheet_client pagination directly.
        if status_filter:
            raw_rows: List[Dict[str, Any]] = await asyncio.to_thread(
                sheet_client.get_sheet_news,
                sheet_url,
                10_000,
                0,
                category,
            )
            # Filter by derived status
            raw_rows = [
                r for r in raw_rows
                if (
                    (status_filter == "uploaded" and (r.get("ai_title") or r.get("ai_content")))
                    or (status_filter == "pending" and not r.get("ai_title") and not r.get("ai_content"))
                    or status_filter not in ("uploaded", "pending")
                )
            ]
            total = len(raw_rows)
            page_rows = raw_rows[offset: offset + limit]
        else:
            # Efficient path: use sheet_client pagination
            raw_rows = await asyncio.to_thread(
                sheet_client.get_sheet_news,
                sheet_url,
                limit,
                offset,
                category,
            )
            # Total count comes from count_sheet_news (uses same cache)
            stats = await asyncio.to_thread(sheet_client.count_sheet_news, sheet_url)
            if category:
                total = stats["by_category"].get(category, 0)
            else:
                total = stats["total"]
            page_rows = raw_rows

        news_items = [_sheet_row_to_news_item(r) for r in page_rows]

        return NewsListResponse(
            news=news_items,
            total=total,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch news from sheet: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch news",
        )


@router.get("/stats", response_model=NewsStatsResponse, status_code=status.HTTP_200_OK)
async def get_news_stats(current_user: User = Depends(get_current_user)):
    """
    Get news statistics from Google Sheet.

    Returns category-wise row counts.  'pending' / 'uploaded' breakdown
    requires reading the full sheet, which may be slow for large sheets;
    results are cached for 30 seconds.
    """
    sheet_url = _get_sheet_url()

    try:
        # Fetch all rows to compute pending/uploaded split
        all_rows: List[Dict[str, Any]] = await asyncio.to_thread(
            sheet_client.get_sheet_news,
            sheet_url,
            10_000,
            0,
            None,
        )

        total = len(all_rows)
        uploaded = sum(
            1 for r in all_rows if r.get("ai_title") or r.get("ai_content")
        )
        pending = total - uploaded

        # Build by_category list compatible with NewsStatsResponse schema
        cat_counts: Dict[str, int] = {}
        for r in all_rows:
            cat = r.get("category") or "기타"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        by_category = [
            {"category": cat, "count": count}
            for cat, count in cat_counts.items()
        ]

        return NewsStatsResponse(
            total=total,
            pending=pending,
            uploaded=uploaded,
            failed=0,  # failure state not tracked in sheet
            by_category=by_category,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch news stats: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch stats",
        )


@router.get("/collect", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def news_collect_info(current_user: User = Depends(get_current_user)):
    """
    Get news collection endpoint info.

    Actual collection is triggered via the process control endpoint.
    """
    return {
        "message": (
            "Use /api/process/news_collection with POST action=start "
            "to trigger news collection"
        ),
        "endpoint": "/api/process/news_collection",
        "method": "POST",
        "body": {
            "action": "start",
            "config": {
                "keywords": {"연애": 15, "경제": 15, "스포츠": 15}
            },
        },
    }


@router.post("/search", status_code=status.HTTP_200_OK)
async def search_news(
    request: NewsSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search Naver News API.

    Searches Naver news with keyword and returns raw results.
    Requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables.
    """
    try:
        result = await asyncio.to_thread(
            _search_naver_news, request.keyword, request.display, request.sort
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("News search failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="News search failed",
        )


@router.post("/save", status_code=status.HTTP_200_OK)
async def save_news(
    request: NewsSaveRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Save news items to Google Sheet.

    Appends items to the sheet.  Duplicates (matched by link) are skipped
    using a live deduplication check against column C.
    """
    sheet_url = _get_sheet_url()

    items = [item.model_dump() for item in request.news_list]

    try:
        result = await asyncio.to_thread(
            _append_news_to_sheet,
            sheet_url,
            items,
            request.category,
        )
        return {
            "message": f"Saved {result['saved']} items, skipped {result['skipped']}",
            "saved": result["saved"],
            "skipped": result["skipped"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("News save failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save news",
        )


@router.delete("/all", status_code=status.HTTP_200_OK)
async def delete_all_news(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete all news rows from Google Sheet.

    Optionally filter by category to delete only rows in that category.
    Requires admin role.
    """
    sheet_url = _get_sheet_url()

    try:
        all_news = await asyncio.to_thread(
            sheet_client.get_sheet_news, sheet_url,
            limit=10_000, offset=0, category=category,
        )
        if not all_news:
            return {"success": True, "deleted_count": 0}

        row_numbers = [item["id"] for item in all_news]
        deleted = await asyncio.to_thread(
            sheet_client.delete_sheet_rows, sheet_url, row_numbers
        )
        return {"success": True, "deleted_count": deleted}
    except Exception as exc:
        logger.error("Bulk delete failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )


@router.delete("/{news_id}", status_code=status.HTTP_200_OK)
async def delete_news(
    news_id: int = FastPath(..., ge=2, description="Sheet row number (>= 2)"),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a single news row from Google Sheet.

    news_id corresponds to the sheet row number (row 1 is header).
    """
    sheet_url = _get_sheet_url()

    try:
        deleted = await asyncio.to_thread(
            sheet_client.delete_sheet_rows, sheet_url, [news_id]
        )
        return {"success": True, "deleted_count": deleted}
    except Exception as exc:
        logger.error("Delete news %d failed: %s", news_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )
