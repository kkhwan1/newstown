# -*- coding: utf-8 -*-
"""
Process Control Routes
Process management endpoints

Optimized with asyncio.to_thread() for blocking operations:
- File I/O for status/log files
- subprocess operations
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from api.schemas.process import ProcessStatusResponse, ProcessActionRequest, ProcessListResponse
from api.dependencies.auth import User, get_current_user, get_current_admin_user

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.process_manager import get_process_manager
from utils.config_manager import get_config_manager

router = APIRouter(prefix="/api/process", tags=["process"])


# Process name mapping
PROCESS_SCRIPTS = {
    "news_collection": "scripts/run_news_collection.py",
    "upload_monitor": "scripts/run_upload_monitor.py",
    "row_deletion": "scripts/run_row_deletion.py",
}


MASKED_VALUE = '***MASKED***'

# Map process names to their config sections for credential recovery
PROCESS_CONFIG_SECTIONS = {
    "news_collection": "news_collection",
    "upload_monitor": "upload_monitor",
    "row_deletion": "row_deletion",
}


def _unmask_config(config: dict, process_name: str) -> dict:
    """Replace ***MASKED*** values with real values from ConfigManager.

    The frontend receives masked credentials from GET /api/config endpoints.
    When it sends that config back to start a process, we need to restore
    the real credential values before passing to the subprocess.
    """
    if not config:
        return config

    has_masked = any(
        v == MASKED_VALUE for v in config.values() if isinstance(v, str)
    )
    if not has_masked:
        return config

    cm = get_config_manager()
    section = PROCESS_CONFIG_SECTIONS.get(process_name)
    if not section:
        return config

    real_config = cm.get(section) or {}
    result = dict(config)
    for key, value in result.items():
        if value == MASKED_VALUE and key in real_config:
            result[key] = real_config[key]
    return result


@router.get("", response_model=ProcessListResponse, status_code=status.HTTP_200_OK)
async def get_all_processes(current_user: User = Depends(get_current_user)):
    """
    Get all process statuses

    Returns the status of all managed processes (running/stopped, PID, runtime).
    Uses thread pool for file I/O operations.
    """
    process_manager = get_process_manager()
    all_status = await asyncio.to_thread(process_manager.get_all_status)

    return ProcessListResponse(processes=all_status)


@router.get("/{process_name}", response_model=ProcessStatusResponse, status_code=status.HTTP_200_OK)
async def get_process_status(process_name: str, current_user: User = Depends(get_current_user)):
    """
    Get specific process status

    Returns detailed status of a specific process.
    Uses thread pool for file I/O operations.
    """
    if process_name not in PROCESS_SCRIPTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown process: {process_name}"
        )

    process_manager = get_process_manager()
    status_info = await asyncio.to_thread(process_manager.get_status, process_name)

    return ProcessStatusResponse(
        name=process_name,
        running=status_info['running'],
        pid=status_info.get('pid'),
        runtime=status_info.get('runtime'),
        start_time=status_info.get('start_time')
    )


@router.post("/{process_name}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def control_process(
    process_name: str,
    request: ProcessActionRequest,
    current_user: User = Depends(get_current_admin_user)  # Admin only
):
    """
    Control process (start/stop)

    Starts or stops a specific process. Admin privileges required.
    Uses thread pool for subprocess operations.
    """
    if process_name not in PROCESS_SCRIPTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown process: {process_name}"
        )

    process_manager = get_process_manager()
    script_path = PROCESS_SCRIPTS[process_name]

    if request.action == "start":
        is_running = await asyncio.to_thread(process_manager.is_running, process_name)
        if is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Process {process_name} is already running"
            )

        # Build config from request, unmasking any ***MASKED*** credentials
        config = request.config or {}
        # DEBUG: Log incoming config
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Process {process_name} start config keys: {list(config.keys())}")
        logger.info(f"Process {process_name} start config sample: {str(config)[:500]}")
        config = _unmask_config(config, process_name)
        logger.info(f"After unmask config keys: {list(config.keys())}")

        # Convert to absolute path
        project_root = Path(__file__).parent.parent.parent
        script_abs_path = str(project_root / script_path)

        success = await asyncio.to_thread(process_manager.start_process, process_name, script_abs_path, config)

        if success:
            return {
                "status": "started",
                "process": process_name
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start process {process_name}"
            )

    elif request.action == "stop":
        is_running = await asyncio.to_thread(process_manager.is_running, process_name)
        if not is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Process {process_name} is not running"
            )

        success = await asyncio.to_thread(process_manager.stop_process, process_name)

        if success:
            return {
                "status": "stopped",
                "process": process_name
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stop process {process_name}"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {request.action}. Must be 'start' or 'stop'"
        )


@router.get("/{process_name}/logs", response_model=Dict[str, str], status_code=status.HTTP_200_OK)
async def get_process_logs(
    process_name: str,
    lines: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Get process logs

    Returns recent log lines from the specified process.
    Uses thread pool for file I/O operations.
    """
    if process_name not in PROCESS_SCRIPTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown process: {process_name}"
        )

    if lines < 1 or lines > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lines must be between 1 and 1000"
        )

    process_manager = get_process_manager()
    logs = await asyncio.to_thread(process_manager.get_logs, process_name, lines)

    return {
        "process": process_name,
        "logs": logs
    }


@router.post("/stop-all", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def stop_all_processes(current_user: User = Depends(get_current_admin_user)):
    """
    Stop all processes

    Stops all running processes. Admin privileges required.
    Uses thread pool for subprocess operations.
    """
    process_manager = get_process_manager()
    await asyncio.to_thread(process_manager.stop_all)

    return {
        "status": "all_stopped"
    }
