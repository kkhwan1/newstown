# -*- coding: utf-8 -*-
"""
Logs Routes
Application log management endpoints
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.dependencies.auth import User, get_current_user, get_current_admin_user

router = APIRouter(prefix="/api/logs", tags=["logs"])


# Response Models
class LogEntry(BaseModel):
    """Log entry"""
    timestamp: str
    level: str
    category: str
    message: str


class LogsResponse(BaseModel):
    """Logs list response"""
    logs: List[LogEntry]
    count: int


def get_log_file_path() -> Path:
    """Get the log file path"""
    # Check for common log locations
    log_dirs = [
        Path(__file__).parent.parent.parent / "logs",
        Path(os.environ.get('TEMP', '/tmp')) / "tynewsauto" / "logs",
        Path(__file__).parent.parent,
    ]

    for log_dir in log_dirs:
        if log_dir.exists():
            # Find most recent log file
            log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.txt"))
            if log_files:
                return max(log_files, key=lambda p: p.stat().st_mtime)

    # If no log file found, return a default path
    return Path(__file__).parent.parent.parent / "app.log"


MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB


def read_log_lines(limit: int = 200, category: Optional[str] = None) -> List[str]:
    """Read log lines from file

    If the log file exceeds MAX_LOG_SIZE (10MB), only the last 10MB is read
    to prevent excessive memory usage.
    """
    log_file = get_log_file_path()

    if not log_file.exists():
        return ["로그 파일이 없습니다."]

    try:
        file_size = os.path.getsize(str(log_file))
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            if file_size > MAX_LOG_SIZE:
                # Seek to last 10MB and skip partial first line
                f.seek(file_size - MAX_LOG_SIZE)
                f.readline()
            lines = f.readlines()

        # Filter by category if specified
        if category:
            category_upper = category.upper()
            lines = [line for line in lines if category_upper in line]

        # Get last N lines
        lines = lines[-limit:] if len(lines) > limit else lines

        return lines

    except Exception as e:
        return [f"로그 읽기 오류: {str(e)}"]


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a log line into structured data"""
    line = line.strip()
    if not line:
        return None

    # Try to parse common log formats
    # Format 1: [2025-01-30 10:00:00] [INFO] [NEWS] Message
    # Format 2: 2025-01-30 10:00:00 INFO NEWS Message

    import re

    # Pattern for [timestamp] [level] [category] message
    pattern1 = r'\[?(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})\]?\s*\[?(\w+)\]?\s*\[?(\w+)\]?\s*(.+)'
    match = re.match(pattern1, line)

    if match:
        timestamp_str, level, category, message = match.groups()
        timestamp = timestamp_str if timestamp_str else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return LogEntry(
            timestamp=timestamp,
            level=level.upper(),
            category=category.upper(),
            message=message.strip()
        )

    # If no match, return as INFO SYSTEM message
    return LogEntry(
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        level="INFO",
        category="SYSTEM",
        message=line
    )


@router.get("", response_model=LogsResponse, status_code=status.HTTP_200_OK)
async def get_logs(
    limit: int = Query(200, ge=1, le=1000, description="Number of log lines to return"),
    category: Optional[str] = Query(None, description="Filter by category (NEWS/UPLOAD/SYSTEM)"),
    current_user: User = Depends(get_current_user)
):
    """
    Get application logs

    Returns log entries with optional filtering by category.
    """
    lines = await asyncio.to_thread(read_log_lines, limit, category)

    log_entries = []
    for line in lines:
        parsed = parse_log_line(line)
        if parsed:
            log_entries.append(parsed)

    return LogsResponse(
        logs=log_entries,
        count=len(log_entries)
    )


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_logs(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Clear application logs

    Deletes the log file. Requires admin role.
    """
    def _clear_log_file():
        log_file = get_log_file_path()
        if log_file.exists():
            log_file.unlink()
            return {"success": True, "message": "Logs cleared successfully"}
        return {"success": True, "message": "No log file to clear"}

    try:
        return await asyncio.to_thread(_clear_log_file)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear logs: {str(e)}"
        )


@router.get("/categories", status_code=status.HTTP_200_OK)
async def get_log_categories(current_user: User = Depends(get_current_user)):
    """
    Get available log categories

    Returns list of categories found in log file.
    """
    lines = await asyncio.to_thread(read_log_lines, 1000, None)

    categories = set()
    for line in lines:
        parsed = parse_log_line(line)
        if parsed and parsed.category != 'SYSTEM':
            categories.add(parsed.category)

    return {
        "categories": sorted(list(categories))
    }
