# -*- coding: utf-8 -*-
"""
FastAPI Server Startup Script

Run this script to start the FastAPI backend server.

Usage:
    python run_api.py

Environment Variables:
    API_HOST: Host to bind to (default: 0.0.0.0)
    API_PORT: Port to bind to (default: 8002)
    JWT_SECRET_KEY: Secret key for JWT token signing
    DEBUG: Enable debug mode (default: false)

API Documentation:
    Swagger UI: http://localhost:8000/docs
    ReDoc: http://localhost:8000/redoc
"""
import os
import sys
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8002"))  # Changed default to 8002 due to port conflicts
    debug = os.getenv("DEBUG", "false").lower() == "true"

    print("=" * 60)
    print("  TyNewsauto FastAPI Server")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print(f"\n📖 API Documentation:")
    print(f"   Swagger UI: http://localhost:{port}/docs")
    print(f"   ReDoc:      http://localhost:{port}/redoc")
    print("=" * 60)

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=debug,
        access_log=True
    )
