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

**No database** — JSON files (`config/`) + Google Sheets only.

**Process management**: `ProcessManager` spawns `scripts/run_*.py` via subprocess. Config passed as `PROCESS_CONFIG` env var (JSON).

**API**: All REST under `/api/`. WebSocket at `/ws/logs?token=JWT`. SPA at `/dashboard`, root `/` is health check. Routes in `api/routes/`: auth, config, process, news, sync, logs, admin, platforms, usage.

**Auth**: JWT (HMAC-SHA256), bcrypt passwords in `config/users.json`. Roles: `admin`/`user`. Default: `admin/admin`. Rate limit: 5/60s on login.

## Critical: Credential Masking Flow

API masks sensitive fields as `***MASKED***` → frontend sends them back → `process.py::_unmask_config()` restores top-level keys only → **subprocess scripts must detect remaining `***MASKED***` and reload from ConfigManager**. Pattern in `run_upload_monitor.py` and `run_news_collection.py`.

## Critical: Column Index Convention

Config values (`title_column`, `content_column`, `completed_column`) are **0-indexed**. F=5, G=6, H=7. But `sheet.update_cell(row, col+1, value)` needs 1-indexed (hence `+1`).

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
# Logs at {tempdir}/tynewsauto/process_logs/{name}.log
```

## Golf Times Upload

Two modes via `config.extra_params.mode`: `user` (default) / `admin`. Form inputs have no `name` attrs — use XPath. Content via `CKEDITOR.instances['FCKeditor1'].setData(html)`. Section: `S1N5`/`S2N28`.

**Platform factory**: Inherit `PlatformUploader` in `utils/platforms/`, register in `__init__.py::platform_map`.

## Naver API Gotcha

Naver returns `description` not `content`. `api.js::saveNews()` maps `item.description → content`. Pydantic `NewsSaveItem` only accepts `content`.

## Required Files (not in git)

- `credentials.json` — Google Service Account key
- `.env` — copy from `.env.example`

## Deployment

- **Docker**: `python:3.11-slim`, port 8080, `entrypoint.sh` decodes `GOOGLE_CREDENTIALS_BASE64`
- **DigitalOcean**: `.do/app.yaml`, `professional-s` instance
