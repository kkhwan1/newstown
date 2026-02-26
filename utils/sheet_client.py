# -*- coding: utf-8 -*-
"""
Google Sheet Client
Thin gspread wrapper for news read/write operations with TTL caching.

@TASK T8 - Google Sheet 직접 연동 클라이언트
@SPEC CLAUDE.md#Architecture
"""
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credentials path (same as naver_to_sheet.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
_CREDENTIALS_PATH = _PROJECT_ROOT / "credentials.json"

_GSPREAD_SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# Simple dict-based TTL cache
# ---------------------------------------------------------------------------
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: int = 30  # seconds
_cache_lock = threading.RLock()


def _get_cached(key: str) -> Optional[Any]:
    """Return cached value if still within TTL, else None."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["time"]) < _cache_ttl:
            return entry["data"]
        return None


def _set_cache(key: str, data: Any) -> None:
    """Store data in cache with current timestamp."""
    with _cache_lock:
        _cache[key] = {"data": data, "time": time.time()}


def _invalidate_cache(prefix: str) -> None:
    """Remove all cache entries whose key starts with prefix."""
    with _cache_lock:
        keys_to_remove = [k for k in list(_cache.keys()) if k.startswith(prefix)]
        for k in keys_to_remove:
            del _cache[k]


# ---------------------------------------------------------------------------
# gspread client / worksheet helpers
# ---------------------------------------------------------------------------

def get_gspread_client():
    """
    Return an authenticated gspread client using credentials.json.

    Raises:
        FileNotFoundError: when credentials.json is missing.
        ImportError: when oauth2client is not installed.
    """
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
    except ImportError as exc:
        raise ImportError(
            "gspread and oauth2client are required. "
            "Install them with: pip install gspread oauth2client"
        ) from exc

    if not _CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {_CREDENTIALS_PATH}. "
            "Download a Google Service Account key and place it there."
        )

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        str(_CREDENTIALS_PATH), _GSPREAD_SCOPE
    )
    client = gspread.authorize(creds)
    return client


def get_worksheet(sheet_url: str):
    """
    Return the first worksheet from the given Google Sheet URL.

    Results are cached for _cache_ttl seconds to reduce API calls.

    Args:
        sheet_url: Full Google Sheets URL.

    Returns:
        gspread.Worksheet instance.
    """
    cache_key = f"ws:{sheet_url}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    client = get_gspread_client()
    doc = client.open_by_url(sheet_url)
    worksheet = doc.get_worksheet(0)
    _set_cache(cache_key, worksheet)
    return worksheet


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_sheet_news(
    sheet_url: str,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Read news rows from the Google Sheet.

    Column layout (1-indexed):
        A(1)=title, B(2)=content, C(3)=link, D(4)=category,
        E(5)=ai_title, F(6)=ai_content

    Header row (row 1) is always skipped.
    Rows are filtered by category (column D) when category is provided.
    A 30-second TTL cache is applied per (sheet_url, category) key to
    avoid hitting Google Sheets rate limits.

    Args:
        sheet_url: Google Sheets URL.
        limit:     Maximum number of rows to return (default 50).
        offset:    Zero-based row offset after filtering (default 0).
        category:  When set, only rows whose column D equals this value
                   are returned.

    Returns:
        List of dicts with keys:
            title, content, link, category,
            ai_title, ai_content, row_number
    """
    cache_key = f"news:{sheet_url}:{category}"
    cached_rows = _get_cached(cache_key)

    if cached_rows is None:
        worksheet = get_worksheet(sheet_url)
        # Fetch all values at once — minimises API calls
        all_values: List[List[str]] = worksheet.get_all_values()

        rows: List[Dict[str, Any]] = []
        # all_values[0] is the header row; data starts at index 1 (row 2)
        for row_idx, row in enumerate(all_values[1:], start=2):
            # Pad short rows so index access is safe (non-mutating to protect cache)
            if len(row) < 6:
                row = row + [""] * (6 - len(row))

            row_category = row[3].strip()  # column D

            if category and row_category != category:
                continue

            # Skip entirely empty rows (title and link both blank)
            title = row[0].strip()
            link = row[2].strip()
            if not title and not link:
                continue

            rows.append(
                {
                    "title": title,
                    "content": row[1].strip(),
                    "link": link,
                    "category": row_category,
                    "ai_title": row[4].strip(),
                    "ai_content": row[5].strip(),
                    "row_number": row_idx,
                }
            )

        _set_cache(cache_key, rows)
        cached_rows = rows

    # Apply pagination on the in-memory list
    return cached_rows[offset: offset + limit]


def count_sheet_news(sheet_url: str) -> Dict[str, Any]:
    """
    Count rows by category.

    Uses the same TTL cache as get_sheet_news (no-category variant) so
    consecutive calls in the same 30-second window cost zero API calls.

    Args:
        sheet_url: Google Sheets URL.

    Returns:
        dict with keys:
            total      (int)  — total non-empty data rows
            by_category (dict) — {category_name: count, ...}
    """
    cache_key = f"news:{sheet_url}:None"
    cached_rows = _get_cached(cache_key)

    if cached_rows is None:
        # Warm the cache by calling get_sheet_news with no filter
        get_sheet_news(sheet_url, limit=10_000, offset=0, category=None)
        cached_rows = _get_cached(cache_key) or []

    by_category: Dict[str, int] = {}
    for row in cached_rows:
        cat = row.get("category") or "기타"
        if not cat:
            cat = "기타"
        by_category[cat] = by_category.get(cat, 0) + 1

    return {"total": len(cached_rows), "by_category": by_category}


def append_news_rows(sheet_url: str, rows: List[List[Any]]) -> int:
    """
    Append rows to the first worksheet.

    Each element of rows should be a list of column values:
        [title, content, link, category]

    The cache is invalidated after a successful write so subsequent reads
    reflect the new data.

    Args:
        sheet_url: Google Sheets URL.
        rows:      List of row arrays to append.

    Returns:
        Number of rows actually appended.
    """
    if not rows:
        return 0

    worksheet = get_worksheet(sheet_url)
    worksheet.append_rows(rows, value_input_option="RAW")

    # Invalidate all cached entries for this sheet
    _invalidate_cache(f"news:{sheet_url}")
    _invalidate_cache(f"ws:{sheet_url}")

    return len(rows)


def get_existing_links(sheet_url: str) -> Set[str]:
    """
    Return the set of all non-empty links currently in column C.

    Uses the cache (no-category variant) when available.

    Args:
        sheet_url: Google Sheets URL.

    Returns:
        Set of URL strings.
    """
    cache_key = f"news:{sheet_url}:None"
    cached_rows = _get_cached(cache_key)

    if cached_rows is None:
        get_sheet_news(sheet_url, limit=10_000, offset=0, category=None)
        cached_rows = _get_cached(cache_key) or []

    return {row["link"] for row in cached_rows if row.get("link")}


def delete_sheet_rows(sheet_url: str, row_numbers: List[int]) -> int:
    """
    Delete rows from Google Sheet by row numbers.

    Rows are deleted in descending order to preserve row numbering.
    Cache is invalidated after deletion.

    Args:
        sheet_url: Google Sheets URL.
        row_numbers: List of row numbers (must be >= 2, row 1 is header).

    Returns:
        Number of rows deleted.
    """
    if not row_numbers:
        return 0

    worksheet = get_worksheet(sheet_url)
    for row_num in sorted(row_numbers, reverse=True):
        worksheet.delete_rows(row_num)

    _invalidate_cache(f"news:{sheet_url}")
    _invalidate_cache(f"ws:{sheet_url}")
    return len(row_numbers)


def get_sheet_row_count(sheet_url: str) -> int:
    """
    Return the total number of non-empty data rows (header excluded).

    Args:
        sheet_url: Google Sheets URL.

    Returns:
        Integer count.
    """
    stats = count_sheet_news(sheet_url)
    return stats["total"]
