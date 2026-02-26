# -*- coding: utf-8 -*-
"""
FastAPI Main Application
TyNewsauto Backend API Server

@TASK T8 - FastAPI Backend Implementation
@SPEC CLAUDE.md#API-Endpoints

Features:
- JWT Authentication
- Configuration Management
- Process Control
- News Management
- Sync Management (Database <-> Google Sheets)
- Log Management with WebSocket real-time streaming
- CORS Support
- Security Headers (CSP, X-Frame-Options, X-Content-Type-Options)
"""
import os
import sys
import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_manager import get_config_manager
from api.routes import auth, config, process, news, sync, logs, admin, platforms, usage
from api.dependencies.auth import get_current_user_ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    print("🚀 Starting FastAPI server...")
    # Initialize config manager
    get_config_manager()
    print("✅ Configuration loaded")

    yield

    # Shutdown: Cleanup
    print("🛑 Shutting down FastAPI server...")


# Create FastAPI app
app = FastAPI(
    title="TyNewsauto API",
    description="Korean news automation system API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
# Default development origins + optional CORS_ORIGINS env var (comma-separated)
origins = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
extra_origins = os.getenv("CORS_ORIGINS", "")
if extra_origins:
    origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Security Headers Middleware
# @TASK T8.3 - Security Headers Implementation
# @SPEC CLAUDE.md#Security
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Content Security Policy - Restrict sources for content
        # Allow same-origin, localhost development, and inline scripts for dashboard
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: http://localhost:* https://localhost:*; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Prevent clickjacking - deny embedding in frames
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS filter (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS (HTTP Strict Transport Security) - only in production with HTTPS
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


app.add_middleware(SecurityHeadersMiddleware)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    print(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": type(exc).__name__ if os.getenv("DEBUG") == "true" else "An error occurred"
        }
    )


# Include Routers
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(process.router)
app.include_router(news.router)
app.include_router(sync.router)
app.include_router(logs.router)
app.include_router(admin.router)
app.include_router(platforms.router)
app.include_router(usage.router)


# WebSocket Connection Manager
# @TASK T8.2 - WebSocket Log Streaming
# @SPEC CLAUDE.md#WebSocket-Endpoint
class LogConnectionManager:
    """Manage WebSocket connections for real-time log streaming"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_log(self, log_entry: dict, user_id: str = None):
        """Send log entry to connected clients"""
        if user_id and user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(log_entry)
                except Exception:
                    # Connection may be closed
                    pass

    async def send_personal_log(self, log_entry: dict, websocket: WebSocket):
        """Send log entry to a specific connection"""
        try:
            await websocket.send_json(log_entry)
        except Exception:
            pass

    def get_connection_count(self, user_id: str = None) -> int:
        """Get count of active connections"""
        if user_id:
            return len(self.active_connections.get(user_id, []))
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
log_manager = LogConnectionManager()


# WebSocket Endpoint for Real-time Log Streaming
@app.websocket("/ws/logs")
async def websocket_logs(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time log streaming

    Connects to receive real-time log updates from the application.
    Requires valid JWT token via query parameter.

    Usage:
        const ws = new WebSocket(`ws://localhost:8000/ws/logs?token=${token}`);
        ws.onmessage = (event) => console.log(JSON.parse(event.data));
    """
    # Authenticate user via shared auth dependency (H4: deduplication)
    user = await get_current_user_ws(websocket, token)
    if user is None:
        return  # get_current_user_ws already closed the connection

    user_id = user.username
    await log_manager.connect(websocket, user_id)

    # Send welcome message
    await log_manager.send_personal_log({
        "type": "connected",
        "message": f"Connected to log stream as {user.username}",
        "timestamp": datetime.datetime.now().isoformat()
    }, websocket)

    # Keep connection alive and handle incoming messages
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await log_manager.send_personal_log({
                    "type": "pong",
                    "timestamp": datetime.datetime.now().isoformat()
                }, websocket)
    except WebSocketDisconnect:
        log_manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        log_manager.disconnect(websocket, user_id)


# Mount static files for HTML dashboard
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve HTML dashboard at root
dashboard_html = Path(__file__).parent.parent / "dashboard.html"


@app.get("/dashboard", tags=["dashboard"])
async def serve_dashboard():
    """Serve the HTML/CSS/JS dashboard"""
    if dashboard_html.exists():
        return FileResponse(str(dashboard_html))
    return JSONResponse(status_code=404, content={"detail": "Dashboard not found"})


# Health Check
@app.get("/", tags=["health"])
async def root():
    """Root endpoint - health check"""
    return {
        "status": "ok",
        "service": "TyNewsauto API",
        "version": "1.0.0",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    cm = get_config_manager()
    sheet_url = cm.get("google_sheet", "url")

    return {
        "status": "healthy",
        "config": "loaded",
        "sheet_configured": bool(sheet_url),
    }


# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")

    print(f"🚀 Starting server on {host}:{port}")
    print(f"📖 API docs: http://{host}:{port}/docs")
    print(f"🔒 ReDoc: http://{host}:{port}/redoc")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG") == "true",
        access_log=True
    )
