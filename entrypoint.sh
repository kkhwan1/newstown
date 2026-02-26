#!/bin/bash
set -e

# Decode Google credentials from base64 env var
if [ -n "$GOOGLE_CREDENTIALS_BASE64" ]; then
    echo "$GOOGLE_CREDENTIALS_BASE64" | base64 -d > /app/credentials.json
    echo "Google credentials file created."
fi

# Initialize config files if first run
python init_db.py

# Start the FastAPI server
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${API_PORT:-8080}" \
    --access-log
