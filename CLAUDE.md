# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean news automation: Naver API → Google Sheets → multi-platform auto-upload (Golf Times, Bizwnews). FastAPI backend + HTML/JS SPA dashboard.

**Production**: `root@129.212.236.253` (port 8001), timezone `Asia/Seoul`
**Dashboard**: `https://candidate-keith-leo-original.trycloudflare.com/dashboard` (Cloudflare Tunnel)

## Commands

```bash
python run_api.py                           # API + Dashboard (default port 8002, API_PORT env overrides)
python scripts/run_news_collection.py       # News collection (dashboard spawns this)
python scripts/run_upload_monitor.py        # Upload monitor
python scripts/run_row_deletion.py          # Row deletion
python init_db.py                           # First-time setup (config files + admin123/admin17730 user)
# API docs: http://localhost:{API_PORT}/docs
```

No test framework, linter, or CI/CD.

## Architecture

```
naver_to_sheet.py → Naver API → Google Sheets (A-D)
                                     ↓
                     Make.com fills E column (AI-generated)
                                     ↓
        Upload monitor reads platform-specific columns → Uploader (Selenium) → Platform site → marks completed column '완료'
                                     ↓
        Row deletion checks ALL platform completed columns → deletes row when all are '완료'
```

**Google Sheet columns** (1-indexed):

| Col | Letter | Content |
|-----|--------|---------|
| 1-4 | A-D | 제목, 본문, 링크, 카테고리 (Naver API) |
| 5 | E | AI 제목 (Make.com) |
| 6-8 | F-H | golftimes 제목, 본문, **완료** |
| 10-12 | J-L | bizwnews 제목, 본문, **완료** |

Platform-specific columns are configured in `upload_platforms` config. **Do not change these values without verifying the actual sheet layout.**

**No database** — JSON files (`config/`) + Google Sheets only.

**Process management**: `ProcessManager` spawns `scripts/run_*.py` via subprocess. Config passed as `PROCESS_CONFIG` env var (JSON).

**API**: All REST under `/api/`. WebSocket at `/ws/logs?token=JWT`. SPA at `/dashboard`, root `/` is health check. Routes in `api/routes/`: auth, config, process, news, sync, logs, admin, platforms, usage. Note: `/stop-all` route must be declared before `/{process_name}` wildcard in `process.py`.

**Auth**: Custom HMAC-SHA256 token (format: `username:timestamp:expiry:signature`), bcrypt passwords in `config/users.json`. Roles: `admin`/`user`. Default: `admin123/admin17730`. `user` role hides Naver API settings, user management, and API usage on the frontend only — all API endpoints except `admin.py` (user CRUD) are accessible to both roles. Rate limit: 5/60s on login (in-memory, per-worker).

**Frontend SPA**: `dashboard.html` + `static/js/`. `app.js` (routing, state in `AppState`, page renderers), `api.js` (REST client with auto-401 logout), `websocket.js` (WS for real-time logs, auto-switches to HTTP polling at `/api/logs?since=ts` after 5 failed reconnects). XSS protected via `escapeHTML()`.

## Critical: Column Index Convention

Platform config values (`title_column`, `content_column`, `completed_column`) in `config_schema.py` are **1-based** (`ge=1`). `run_upload_monitor.py` converts these to **0-based** on read (`raw_value - 1`) for array access. The `enumerate()` header-detection fallback is already 0-based. `sheet.update_cell(row, col, value)` expects 1-based — so when writing back, add 1 to 0-based indices. Array access from `sheet.get_all_values()` is always 0-based (`row[0]`=A).

**Current production values**: golftimes=`6,7,8` (F,G,H), bizwnews=`10,11,12` (J,K,L). Row deletion hardcodes `COMPLETED_COLUMNS = [8, 12]` (H + L).

## Critical: Credential Masking Flow

API masks sensitive fields as `***MASKED***` → frontend sends them back → `process.py::_unmask_config()` restores top-level keys only → **subprocess scripts must detect remaining `***MASKED***` and reload from ConfigManager**. Pattern in `run_upload_monitor.py` and `run_news_collection.py`. Applies to all platform credentials (golftimes, bizwnews).

## Critical: Async + Thread Safety

- Use `asyncio.to_thread()` for blocking I/O in async routes (gspread, file I/O)
- `ConfigManager` uses `RLock` (reentrant) — `set()`/`set_section()` hold lock through `_save_to_json()` for atomic updates
- `_save_to_json()` and `auth_store._write_raw()` use temp file + `os.replace()` for crash-safe atomic writes
- `sheet_client.py`: `RLock` protects TTL cache (30s); pad rows with `row + [""]*(n)` (new list, don't mutate cache)
- Always `ensure_ascii=False` for JSON dumps; subprocess env sets `PYTHONIOENCODING=utf-8`

## Key APIs

```python
# ConfigManager (singleton, thread-safe with RLock)
cm = get_config_manager()
cm.get("news_collection", "display_count", default=30)
cm.get_news_config()      # Full config with sheet_url, naver keys, category_keywords
cm.get_upload_config()    # Upload config with sheet_url
cm.get_deletion_config()  # Deletion config with sheet_url, completed_columns

# ProcessManager
pm = ProcessManager()
pm.start_process("news_collection", "scripts/run_news_collection.py", config={...})
# Logs: {tempdir}/tynewsauto/process_logs/{name}.log  (Windows: %TEMP%, Linux: /tmp)
# Status: {tempdir}/tynewsauto/process_status.json
```

## Config Sections (`dashboard_config.json`)

`news_collection` (keywords, display_count, sort) | `category_keywords` ({category}.core[], .general[]) | `upload_monitor` (check_interval, completed_column, concurrent_uploads) | `row_deletion` (delete_interval, max_delete_count) | `google_sheet` (url) | `naver_api` (client_id, client_secret) | `golftimes` (site_id, site_pw) | `bizwnews` (site_id, site_pw) | `upload_platforms` ({name}.enabled/title_column/content_column/completed_column/credentials_section) | `news_schedule` (enabled, interval_hours). Pydantic schemas in `utils/config_schema.py`. Env vars override JSON via `ConfigManager._apply_env_overrides()`.

## Platform Upload

Two platforms sharing same CMS (different sites): **Golf Times** (`golftimes.py`, sections S1N5/S2N28) and **Bizwnews** (`bizwnews.py`, sections S1N2/S2N26). Both use Selenium + XPath (no `name` attrs on form inputs). Content via `CKEDITOR.instances['FCKeditor1'].setData(html)`.

Golftimes has two modes via `config.extra_params.mode`: `user` (default) / `admin`. Bizwnews preserves CKEditor header (`[비즈월드]`) and footer (`[비즈월드=reporter]`) during content insertion.

**Row deletion**: `run_row_deletion.py` checks `COMPLETED_COLUMNS = [8, 12]` (H + L columns). Rows are deleted only when **all** platform completed columns contain "완료".

**Platform factory**: To add a platform: (1) Create `utils/platforms/newname.py` inheriting `PlatformUploader` from `base.py`, (2) Implement `login()`, `upload(title, content, category)`, `from_config()`, (3) Register in `__init__.py::platform_map`, (4) Add credentials section + `PlatformConfig` entry in config. `DriverPool` in `__init__.py` provides Chrome WebDriver pooling for concurrent uploads.

## Naver API Gotcha

Naver returns `description` not `content`. `api.js::saveNews()` maps `item.description → content`. Pydantic `NewsSaveItem` only accepts `content`.

## Required Files (not in git)

- `credentials.json` — Google Service Account key
- `config/dashboard_config.json` — runtime config (contains credentials, excluded from git)
- `config/users.json` — user accounts (excluded from git)
- `.env` — copy from `.env.example`

## Deployment

- **Docker**: `python:3.11-slim`, port 8080, `entrypoint.sh` decodes `GOOGLE_CREDENTIALS_BASE64`
- **DigitalOcean**: `.do/app.yaml`, `professional-s` instance
- **Production server**: SSH `root@129.212.236.253`, project at `/root/tynewsauto`, managed by systemd (`systemctl restart tynewsauto`). Deploy: `git pull && systemctl restart tynewsauto`. Server timezone: `Asia/Seoul`.
