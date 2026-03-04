# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean news automation: Naver API → Google Sheets → Golf Times auto-upload. FastAPI backend + HTML/JS SPA dashboard.

**Production**: `root@129.212.236.253` (port 8001)
**Dashboard**: `https://candidate-keith-leo-original.trycloudflare.com/dashboard` (Cloudflare Tunnel)

## Commands

```bash
python run_api.py                           # API + Dashboard (default port 8002, API_PORT env overrides)
python scripts/run_news_collection.py       # News collection (dashboard spawns this)
python scripts/run_upload_monitor.py        # Upload monitor
python scripts/run_row_deletion.py          # Row deletion
python init_db.py                           # First-time setup (config files + admin/admin user)
# API docs: http://localhost:{API_PORT}/docs
```

No test framework, linter, or CI/CD.

## Architecture

```
naver_to_sheet.py → Naver API → Google Sheets (A-D)
                                     ↓
                     Make.com fills E-G (AI-generated title/content)
                                     ↓
                Upload monitor reads F/G → GolftimesUploader → Golf Times → marks H '완료'
```

**Sheet columns** (1-indexed for gspread): A=제목, B=본문, C=링크, D=카테고리 | E=AI_제목, F=AI_본문 (Make.com fills) | H=완료 marker | J=platform_title(10), K=platform_content(11), L=platform_completed(12) for golftimes.

**No database** — JSON files (`config/`) + Google Sheets only.

**Process management**: `ProcessManager` spawns `scripts/run_*.py` via subprocess. Config passed as `PROCESS_CONFIG` env var (JSON).

**API**: All REST under `/api/`. WebSocket at `/ws/logs?token=JWT`. SPA at `/dashboard`, root `/` is health check. Routes in `api/routes/`: auth, config, process, news, sync, logs, admin, platforms, usage.

**Auth**: JWT (HMAC-SHA256), bcrypt passwords in `config/users.json`. Roles: `admin`/`user`. Default: `admin123/admin17730`. `user` role hides Naver API settings, user management, and API usage in the settings page. Rate limit: 5/60s on login.

**Frontend SPA**: `dashboard.html` + `static/js/`. `app.js` (routing, state in `AppState`, page renderers), `api.js` (REST client with auto-401 logout), `websocket.js` (WS for real-time logs, auto-switches to HTTP polling at `/api/logs?since=ts` after 5 failed reconnects). XSS protected via `escapeHTML()`.

## Critical: Credential Masking Flow

API masks sensitive fields as `***MASKED***` → frontend sends them back → `process.py::_unmask_config()` restores top-level keys only → **subprocess scripts must detect remaining `***MASKED***` and reload from ConfigManager**. Pattern in `run_upload_monitor.py` and `run_news_collection.py`.

## Critical: Column Index Convention

Platform config values (`title_column=10`, `content_column=11`, `completed_column=12`) in `config_schema.py` are **1-based** (`ge=1`). `upload_monitor.completed_column=8` (H column, 1-based). However, `run_upload_monitor.py` auto-detects columns via `enumerate()` (0-based) as fallback. Code uses `sheet.update_cell(row, col+1, value)` — **verify whether platform_config values need the +1 or not** when modifying column logic. Array access from `sheet.get_all_values()` is always 0-based (`row[0]`=A).

## Critical: Async + Thread Safety

- Use `asyncio.to_thread()` for blocking I/O in async routes (gspread, file I/O)
- `sheet_client.py`: `RLock` protects TTL cache; pad rows with `row + [""]*(n)` (new list, don't mutate cache)
- Always `ensure_ascii=False` for JSON dumps; subprocess env sets `PYTHONIOENCODING=utf-8`

## Key APIs

```python
# ConfigManager
cm = get_config_manager()
cm.get("news_collection", "display_count", default=30)
cm.get_news_config()      # Full config with sheet_url, naver keys, category_keywords
cm.get_upload_config()    # Upload config with sheet_url
cm.get_deletion_config()  # Deletion config with sheet_url, completed_column

# ProcessManager
pm = ProcessManager()
pm.start_process("news_collection", "scripts/run_news_collection.py", config={...})
# Logs: {tempdir}/tynewsauto/process_logs/{name}.log  (Windows: %TEMP%, Linux: /tmp)
# Status: {tempdir}/tynewsauto/process_status.json
```

## Config Sections (`dashboard_config.json`)

`news_collection` (keywords, display_count, sort) | `category_keywords` ({category}.core[], .general[]) | `upload_monitor` (check_interval, completed_column, concurrent_uploads) | `row_deletion` (delete_interval, max_delete_count) | `google_sheet` (url) | `naver_api` (client_id, client_secret) | `golftimes` (site_id, site_pw) | `upload_platforms` ({name}.enabled/title_column/content_column/completed_column/credentials_section) | `news_schedule` (enabled, interval_hours). Pydantic schemas in `utils/config_schema.py`. Env vars override JSON via `ConfigManager._apply_env_overrides()`.

## Golf Times Upload

Two modes via `config.extra_params.mode`: `user` (default) / `admin`. Form inputs have no `name` attrs — use XPath. Content via `CKEDITOR.instances['FCKeditor1'].setData(html)`. Section: `S1N5`/`S2N28`.

**Platform factory**: To add a platform: (1) Create `utils/platforms/newname.py` inheriting `PlatformUploader` from `base.py`, (2) Implement `login()`, `upload(title, content, category)`, `from_config()`, (3) Register in `__init__.py::platform_map`, (4) Add credentials section + `PlatformConfig` entry in config.

## Naver API Gotcha

Naver returns `description` not `content`. `api.js::saveNews()` maps `item.description → content`. Pydantic `NewsSaveItem` only accepts `content`.

## Required Files (not in git)

- `credentials.json` — Google Service Account key
- `.env` — copy from `.env.example`

## Deployment

- **Docker**: `python:3.11-slim`, port 8080, `entrypoint.sh` decodes `GOOGLE_CREDENTIALS_BASE64`
- **DigitalOcean**: `.do/app.yaml`, `professional-s` instance
