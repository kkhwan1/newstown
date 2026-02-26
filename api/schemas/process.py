# -*- coding: utf-8 -*-
"""
Process Control Schemas
Process status and action models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ProcessStatusResponse(BaseModel):
    """Single process status response"""
    name: str = Field(..., description="Process name")
    running: bool = Field(..., description="Whether process is running")
    pid: Optional[int] = Field(None, description="Process ID")
    runtime: Optional[str] = Field(None, description="Process runtime (HH:MM:SS)")
    start_time: Optional[str] = Field(None, description="Process start time (ISO format)")


class ProcessActionRequest(BaseModel):
    """Process action request"""
    action: str = Field(..., pattern="^(start|stop)$", description="Action: start or stop")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration for start action")


class ProcessListResponse(BaseModel):
    """All processes status response"""
    processes: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Process name -> status mapping")
