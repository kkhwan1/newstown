# TyNewsauto FastAPI Backend

FastAPI-based REST API server for the TyNewsauto Korean news automation system.

## Features

- **JWT Authentication**: Secure token-based authentication
- **Configuration Management**: Get and update application configuration
- **Process Control**: Start/stop background processes (news collection, upload monitoring, row deletion)
- **News Management**: Query news articles and statistics from PostgreSQL database
- **CORS Support**: Cross-origin resource sharing for Streamlit dashboard
- **API Documentation**: Auto-generated Swagger UI and ReDoc

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and set required variables:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/tynewsauto
JWT_SECRET_KEY=your-secret-key-generate-with-python-secrets
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Initialize Database

```bash
python init_db.py
```

This creates:
- Database tables (`news`, `prompts`, `users`, `settings`)
- Default admin user (username: `admin`, password: `admin`)

**⚠️ Change the default admin password immediately!**

### 4. Start API Server

```bash
python run_api.py
```

Or directly with uvicorn:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login with username/password |
| GET | `/api/auth/me` | Get current user info |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get full configuration |
| POST | `/api/config` | Update configuration (admin only) |
| GET | `/api/config/news` | Get news collection config |
| GET | `/api/config/upload` | Get upload monitor config |
| GET | `/api/config/platforms` | Get platforms config |

### Process Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/process` | Get all process statuses |
| GET | `/api/process/{name}` | Get specific process status |
| POST | `/api/process/{name}` | Start/stop process (admin only) |
| GET | `/api/process/{name}/logs` | Get process logs |

### News

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/news` | Get news list (paginated) |
| GET | `/api/news/stats` | Get news statistics |

## Authentication

### Login Request

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Response

```json
{
  "access_token": "admin:1234567890:abcdef123456...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

### Using Token

```bash
curl http://localhost:8000/api/config \
  -H "Authorization: Bearer admin:1234567890:abcdef123456..."
```

## Process Names

| Name | Description | Script |
|------|-------------|--------|
| `news_collection` | News collection from Naver | `scripts/run_news_collection.py` |
| `upload_monitor` | Upload monitoring to platforms | `scripts/run_upload_monitor.py` |
| `row_deletion` | Completed row deletion | `scripts/run_row_deletion.py` |

## Example: Start News Collection

```bash
TOKEN="your-token-here"

# Start process
curl -X POST http://localhost:8000/api/process/news_collection \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "config": {
      "keywords": {"연애": 15, "경제": 15, "스포츠": 15}
    }
  }'

# Check status
curl http://localhost:8000/api/process/news_collection \
  -H "Authorization: Bearer $TOKEN"

# Stop process
curl -X POST http://localhost:8000/api/process/news_collection \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}'
```

## Testing

Run the test script to verify the API:

```bash
python test_api.py
```

## Development

### Project Structure

```
api/
├── __init__.py
├── main.py                 # FastAPI application
├── dependencies/           # Dependencies (auth, database)
│   ├── __init__.py
│   ├── auth.py            # JWT authentication
│   └── database.py        # Database connection
├── routes/                # API routes
│   ├── __init__.py
│   ├── auth.py           # Authentication endpoints
│   ├── config.py         # Configuration endpoints
│   ├── process.py        # Process control endpoints
│   └── news.py           # News endpoints
└── schemas/              # Pydantic models
    ├── __init__.py
    ├── auth.py           # Auth request/response
    ├── config.py         # Config models
    ├── process.py        # Process models
    └── news.py           # News models
```

### Adding New Endpoints

1. Create schema in `api/schemas/`
2. Create route in `api/routes/`
3. Register in `api/main.py`:

```python
from api.routes import your_new_router
app.include_router(your_new_router.router)
```

## Security Notes

1. **JWT Secret Key**: Generate a secure random key:
   ```python
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Change Default Password**: The default admin password is `admin`. Change it immediately after first login.

3. **HTTPS**: Use HTTPS in production with a reverse proxy (nginx, Traefik).

4. **CORS**: Configure allowed origins in `api/main.py` for production.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes* | - | PostgreSQL connection URL |
| `JWT_SECRET_KEY` | Yes | - | Secret for JWT signing |
| `API_HOST` | No | 0.0.0.0 | Host to bind to |
| `API_PORT` | No | 8000 | Port to bind to |
| `DEBUG` | No | false | Enable debug mode |

*Required for full functionality. API can run without database but with limited features.

## Troubleshooting

### Database Connection Failed

```
Error: Database not configured
```

**Solution**: Set `DATABASE_URL` in `.env` file and ensure PostgreSQL is running.

### Import Error

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### Token Validation Failed

```
401 Unauthorized: Could not validate credentials
```

**Solution**: Ensure `JWT_SECRET_KEY` is set and consistent between server and client.

## License

Part of the TyNewsauto project.
