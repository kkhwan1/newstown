# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean news automation system that collects news from Naver, stores in Google Sheets, and auto-uploads to Golf Times via Selenium browser automation. Features FastAPI backend with HTML/CSS/JS SPA dashboard, WebSocket real-time log streaming, and JWT authentication.

**Requirements**: Python 3.10+, Chrome browser (for Selenium upload features).

## Quick Start

```bash
pip install -r requirements.txt
copy .env.example .env          # Edit with real values
python init_db.py               # First time only - creates config JSON files + admin/admin user
python run_api.py               # Dashboard at http://localhost:{API_PORT}/dashboard
```

Minimal `.env` for development:
```env
JWT_SECRET_KEY=dev-secret-key-change-in-production
```

Full env var reference: see `.env.example`. Key required vars: `JWT_SECRET_KEY`, `GOOGLE_SHEET_URL`, `GOLFTIMES_ID`/`GOLFTIMES_PW`, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`.

**Port**: `run_api.py` defaults to **8002**, but `API_PORT` env var overrides it. Current `.env` sets `API_PORT=8000`.

## Common Commands

```bash
# FastAPI backend + SPA dashboard
python run_api.py

# News collection
python naver_to_sheet.py                        # Direct
python scripts/run_news_collection.py           # Via wrapper (dashboard spawns this)

# Auto-upload monitoring
python scripts/run_upload_monitor.py

# Row deletion
python scripts/run_row_deletion.py

# API docs: http://localhost:{API_PORT}/docs (Swagger) or /redoc
```

There is no test framework (pytest/unittest), linter config, or CI/CD pipeline.

## Architecture

### Data Flow Pipeline

```
naver_to_sheet.py → Naver API → Google Sheets (A-D columns)
                                        |
                        Make.com (external) fills E/F columns (AI-generated)
                                        |
                    Upload monitors read E/F → Platform uploader → Golf Times
```

### Key Architectural Patterns

**No database** — All data storage uses JSON files (`config/`) and Google Sheets. No SQLite or PostgreSQL.

**Process management via subprocesses**: Dashboard starts background processes via `ProcessManager` which spawns `scripts/run_*.py` wrappers. Config is passed via `PROCESS_CONFIG` environment variable (JSON-serialized). **Critical**: When starting processes via API, config MUST be included in the request body — use `ConfigManager.get_news_config()` (or `get_upload_config()`, `get_deletion_config()`) to assemble the full config including `sheet_url`, `naver_client_id`, `category_keywords` etc.

**Configuration**: `config/dashboard_config.json` (single source) → `.env` (credentials override). `ConfigManager._load()` merges `DEFAULT_CONFIG` with JSON file data so missing sections always have defaults. Sensitive fields (naver_api, golftimes credentials) are masked as `***MASKED***` in API responses; `api/routes/process.py` unmasks them before subprocess launch.

**Authentication**: `config/users.json` stores bcrypt password hashes. `utils/auth_store.py` provides CRUD operations with atomic writes (`tempfile` + `os.replace`) and username validation (`^[a-zA-Z0-9_-]{1,100}$`). Two roles: `admin` and `user`.

**Platform upload abstraction**: Factory pattern in `utils/platforms/`. All uploaders inherit `PlatformUploader` ABC from `base.py`. Register new platforms in `__init__.py`'s `platform_map` dict.

### API Structure

FastAPI app assembled in `api/main.py` with:
- CORS middleware (origins: localhost:8501, :3000, :8000)
- `SecurityHeadersMiddleware` — CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff
- Global exception handler (hides internals in non-debug mode)
- Routes in `api/routes/`: `auth.py`, `config.py`, `process.py`, `news.py`, `sync.py`, `logs.py`, `admin.py`, `platforms.py`, `usage.py`

All REST endpoints under `/api/` prefix. WebSocket at `/ws/logs?token=JWT`. SPA served at `/dashboard` (root `/` is health check).

**Authorization**: `get_current_user()` for authenticated routes, `get_current_admin_user()` for admin-only (all delete endpoints, user management, config writes). Schemas in `api/schemas/`.

### Frontend SPA (`static/js/`)

Three files: `api.js` (API communication layer), `websocket.js` (real-time log streaming with ping/pong keep-alive), `app.js` (page handlers + `AppState` state management + `Utils` for toast/escapeHTML/caching).

**Naver API field mapping**: Naver search returns `description` field, not `content`. The `api.js` `saveNews()` maps `item.description → content` before sending to backend. The Pydantic `NewsSaveItem` model only accepts `content`, so this mapping is critical.

**Browser cache**: After editing JS files, Chrome may serve cached versions. Always hard-refresh (Ctrl+Shift+R) when testing frontend changes.

### Google Sheets Column Layout

| Column | Content | Source |
|--------|---------|--------|
| A | Original title | Naver API |
| B | Original content | Naver API (description field) |
| C | Link | Naver API |
| D | Category (연애/경제/스포츠) | Auto-classified |
| E | AI Title | Make.com |
| F | AI Content | Make.com |
| J-L | Upload title/content/status | Configurable per platform |

## Critical Patterns

### Async Routes with Blocking I/O

Use `asyncio.to_thread()` for blocking operations in FastAPI async routes (gspread calls, file I/O).

### Thread Safety

- `utils/sheet_client.py`: `threading.RLock` protects the TTL cache dict. RLock (reentrant) is necessary because `count_sheet_news()` calls `_get_cached()` then may call `get_sheet_news()` which calls `_set_cache()`.
- `utils/auth_store.py`: `threading.Lock` for atomic JSON file operations (read-modify-write).
- Cache list mutation: `get_sheet_news()` pads short rows with `row = row + [""] * (6 - len(row))` (creates new list) instead of `row.append()` which would mutate cached data.

### UTF-8 Encoding

Always use `ensure_ascii=False` for JSON dumps. Subprocess environments set `PYTHONIOENCODING=utf-8`.

### Input Validation

- `news.py` search: `sort` parameter uses `Literal["date", "sim"]` — Pydantic rejects other values with 422.
- Error responses: HTTP 500 errors use generic messages (e.g., `"Failed to fetch news"`), never exposing internal exception details. `logger.error()` records full details server-side.

## Configuration

### ConfigManager API (`utils/config_manager.py`)

```python
from utils.config_manager import get_config_manager
cm = get_config_manager()
cm.get("news_collection", "display_count", default=30)
cm.set_section("news_collection", {...}, save=True)
cm.get_news_config()        # Full config with sheet_url, naver keys, category_keywords
cm.get_upload_config()       # Upload config with sheet_url
cm.get_deletion_config()     # Deletion config with sheet_url, completed_column
```

### ProcessManager (`utils/process_manager.py`)

```python
from utils.process_manager import ProcessManager
pm = ProcessManager()
pm.start_process("news_collection", "scripts/run_news_collection.py", config={...})
pm.get_status("news_collection")  # {"running": bool, "pid": int, ...}
pm.stop_process("news_collection")
```

### Auth Store (`utils/auth_store.py`)

```python
from utils.auth_store import get_user, create_user, update_user, delete_user, get_all_users
user = get_user("admin")           # Returns dict with id, username, password_hash, role
create_user("newuser", hash, "user")  # role must be "admin" or "user"
update_user("admin", {"password_hash": new_hash})  # Only password_hash and role allowed
```

### Sheet Client (`utils/sheet_client.py`)

```python
from utils.sheet_client import get_sheet_news, count_sheet_news, append_news_rows, delete_sheet_rows
news = get_sheet_news(sheet_url, limit=50, category="경제")  # 30s TTL cache, thread-safe
stats = count_sheet_news(sheet_url)  # {total, by_category}
delete_sheet_rows(sheet_url, [5, 3])  # Deletes rows in descending order, invalidates cache
```

## Security

- **JWT**: HMAC-SHA256, format `username:timestamp:expiry:signature`. Default credentials `admin/admin` (triggers password change prompt on first login).
- **Passwords**: bcrypt hashing with auto-migration from legacy SHA256 hashes. Auth logic in `api/dependencies/auth.py`. Users stored in `config/users.json`.
- **Rate limiting**: In-memory IP-based, 5 attempts per 60 seconds on `/api/auth/login`.
- **Security headers**: CSP with `connect-src 'self' ws://localhost:*`, X-Frame-Options: DENY, HSTS in production.

## JSON Config Files

| File | Purpose | In .gitignore |
|------|---------|---------------|
| `config/dashboard_config.json` | All runtime settings | Yes |
| `config/users.json` | User accounts (bcrypt hashes) | Yes |
| `config/naver_api.json` | Naver API keys | Yes |
| `config/api_usage.json` | Daily API call counter | Yes |

## Platform-Specific: Golf Times

- **Form has no name attributes** — use XPath: `//input[@type='text']`, `//input[@type='password']`
- Content injection: `CKEDITOR.instances['FCKeditor1'].setData(content)`
- Writer selection: `writerSet('tymedia', '김한솔', 'master@thegolftimes.co.kr', '기자')`
- Submit: `newsWriteFormSubmit(document.newsWriteForm)`
- Set `headless=False` in platform config for visual Selenium debugging

## Adding New Platforms

1. Create class inheriting `PlatformUploader` in `utils/platforms/` with `login()`, `upload()`, `from_config()`
2. Register in `utils/platforms/__init__.py` `platform_map`
3. Add platform config via dashboard or `config/dashboard_config.json`

## Required Files (not in git)

- `credentials.json` — Google Service Account key (share email with Sheet as Editor)
- `.env` — Environment variables (copy from `.env.example`)
