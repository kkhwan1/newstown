# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean news automation: Naver API → Google Sheets → multi-platform auto-upload (Golf Times, Bizwnews). FastAPI backend + HTML/JS SPA dashboard.

**Production**: `root@129.212.236.253` (port 8001), timezone `Asia/Seoul`
**Dashboard**: `https://compromise-finest-dinner-getting.trycloudflare.com/dashboard` (Cloudflare Quick Tunnel — URL changes on cloudflared restart)
**Direct access**: `http://129.212.236.253:8001/dashboard` (stable, no HTTPS)

## Commands

```bash
python run_api.py                           # API + Dashboard (default port 8002, API_PORT env overrides)
python scripts/run_news_collection.py       # News collection (dashboard spawns this)
python scripts/run_upload_monitor.py        # Upload monitor
python scripts/run_row_deletion.py          # Row deletion
python init_db.py                           # First-time setup (config files + admin123/admin17730 user)
# API docs: http://localhost:{API_PORT}/docs
```

No test framework, linter, or CI/CD. Manual test helpers in `scripts/test_*.py`.

## Architecture

```
naver_to_sheet.py → Naver API → Google Sheets (A-D, E=pubDate)
                                     ↓
                     Make.com fills platform AI columns (F-G, J-K)
                                     ↓
        Upload monitor reads platform-specific columns → Uploader (Selenium) → Platform site → marks completed column '완료'
                                     ↓
        Row deletion checks ALL platform completed columns → deletes row when all are '완료'
```

**Google Sheet columns** (1-indexed):

| Col | Letter | Content |
|-----|--------|---------|
| 1-4 | A-D | 제목, 본문, 링크, 카테고리 (Naver API) |
| 5 | E | 뉴스 발행시점 (`260315_18:04` 형식, `format_pub_date()`) |
| 6-8 | F-H | golftimes AI제목, AI본문, **완료** |
| 10-12 | J-L | bizwnews AI제목, AI본문, **완료** |
| 14-16 | N-P | redian AI제목, AI본문, **완료** |
| 18-20 | R-T | dailypop AI제목, AI본문, **완료** |

Platform-specific columns are configured in `upload_platforms` config. **Do not change these values without verifying the actual sheet layout.**

**No database** — JSON files (`config/`) + Google Sheets only. (Legacy `tynewsauto.db`, `.db-shm`, `.db-wal` files remain in project root but are unused — safe to delete.)

**Process management**: `ProcessManager` (singleton) spawns `scripts/run_*.py` via subprocess with `start_new_session=True`. Config passed as `PROCESS_CONFIG` env var (JSON). File-based status at `{tempdir}/tynewsauto/process_status.json` survives API restarts; validates PIDs on init to discard stale entries.

**API**: All REST under `/api/`. WebSocket at `/ws/logs?token=JWT`. SPA at `/dashboard`, root `/` is health check. Routes in `api/routes/`: auth, config, process, news, sync, logs, admin, platforms, usage. Note: `/stop-all` route must be declared before `/{process_name}` wildcard in `process.py`. `SecurityHeadersMiddleware` in `api/main.py` adds CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy headers.

**Audit logging**: `utils/logger.py::audit_log()` writes JSON audit trail to `logs/audit.log` for admin actions (login, logout, password_change, process_start/stop, config_change). Separate from process activity logs.

**Auth**: Custom HMAC-SHA256 token (format: `username:timestamp:expiry:signature`), bcrypt passwords in `config/users.json`. Roles: `admin`/`user`. Default: `admin123/admin17730`. `user` role hides Naver API settings, user management, and API usage on the frontend only — all API endpoints except `admin.py` (user CRUD) are accessible to both roles. Rate limit: 5/60s on login (in-memory, per-worker).

**Frontend SPA**: `dashboard.html` + `static/js/`. `app.js` (routing, state in `AppState`, page renderers), `api.js` (REST client with auto-401 logout), `websocket.js` (WS for real-time logs, auto-switches to HTTP polling at `/api/logs?since=ts` after 5 failed reconnects). XSS protected via `escapeHTML()`. Keyword settings use tag/chip UI (`.kw-tag` with X delete + Enter to add, auto-saves). Platform selection shows per-platform category checkboxes (`.category-chip`).

## Critical: CSS Variables

`style.css` defines `--color-primary` (#111) and `--color-secondary` (#fff), NOT `--primary`. Always use `var(--color-primary)` for themed colors. Other variables: `--bg-primary`, `--bg-secondary`, `--bg-tertiary`, `--text-primary`, `--text-secondary`, `--border-color`, `--border-light`, `--radius-sm`, `--radius-md`.

## Critical: Column Index Convention

Platform config values (`title_column`, `content_column`, `completed_column`) in `config_schema.py` are **1-based** (`ge=1`). `run_upload_monitor.py` converts these to **0-based** on read (`raw_value - 1`) for array access. The `enumerate()` header-detection fallback is already 0-based. `sheet.update_cell(row, col, value)` expects 1-based — so when writing back, add 1 to 0-based indices. Array access from `sheet.get_all_values()` is always 0-based (`row[0]`=A).

**Current production values**: golftimes=`6,7,8` (F,G,H), bizwnews=`10,11,12` (J,K,L), redian=`14,15,16` (N,O,P), dailypop=`18,19,20` (R,S,T). Row deletion hardcodes `COMPLETED_COLUMNS = [8, 12, 16, 20]` (H + L + P + T).

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

`news_collection` (keywords, display_count, sort) | `category_keywords` ({category}.core[], .general[]) | `upload_monitor` (check_interval, completed_column, concurrent_uploads) | `row_deletion` (delete_interval, max_delete_count) | `google_sheet` (url) | `naver_api` (client_id, client_secret) | `golftimes` (site_id, site_pw) | `bizwnews` (site_id, site_pw) | `redian` (site_id, site_pw) | `dailypop` (site_id, site_pw) | `upload_platforms` ({name}.enabled/title_column/content_column/completed_column/credentials_section/**allowed_categories**) | `news_schedule` (enabled, interval_hours). Pydantic schemas in `utils/config_schema.py`. Env vars override JSON via `ConfigManager._apply_env_overrides()`.

## Platform Upload

Four platforms sharing same CMS (NDSOFT, different sites):

| Platform | File | Sections | URL | Notes |
|----------|------|----------|-----|-------|
| Golf Times | `golftimes.py` | S1N5/S2N28 | thegolftimes.co.kr | user/admin 모드 |
| Bizwnews | `bizwnews.py` | S1N2/S2N26 | bizwnews.com | [비즈월드] 헤더/푸터 보존 |
| Redian | `redian.py` | S1N10 (1차만) | redian.org → cms.redian.org | 2차 섹션 없음 |
| DailyPop | `dailypop.py` | S1N10 (1차만) | dailypop.kr | 저장 버튼: `button.expanded.large` (success 없음) |

All use Selenium + CKEditor (`FCKeditor1`). Content via `CKEDITOR.instances['FCKeditor1'].setData(html)`.

Golftimes has two modes via `config.extra_params.mode`: `user` (default) / `admin`. Bizwnews preserves CKEditor header (`[비즈월드]`) and footer (`[비즈월드=reporter]`) during content insertion. Redian/DailyPop have no header/footer patterns.

**Per-platform category filtering**: Each platform has `allowed_categories` (list of strings, empty=all). Upload monitor reads column D (category, 0-based index 3) and skips rows whose category is not in the list. Config example: `golftimes: ["연애","경제","스포츠"]`, `bizwnews: ["경제"]`. Dashboard shows category checkboxes per platform.

**Row deletion**: `run_row_deletion.py` checks `COMPLETED_COLUMNS = [8, 12, 16, 20]` (H + L + P + T columns). Rows are deleted only when **all** platform completed columns contain "완료".

**Platform factory**: To add a platform: (1) Create `utils/platforms/newname.py` inheriting `PlatformUploader` from `base.py`, (2) Implement `login()`, `upload(title, content, category)`, `from_config()`, (3) Register in `__init__.py::platform_map`, (4) Add credentials section + `PlatformConfig` entry in config. `DriverPool` in `__init__.py` provides Chrome WebDriver pooling for concurrent uploads.

## Critical: News Deduplication System

`naver_to_sheet.py`의 뉴스 수집은 5단계 중복 판정 + 최종 저장 전 검증 + 재검색 루프로 구성.

**중복 판정 순서** (각 뉴스 아이템마다):
1. URL 정규화 (`normalize_url()`) + `all_news_links` set 비교
2. `check_duplicate_in_cache()` — 링크 + 제목 유사도 (시트 캐시 대비, SequenceMatcher + Jaccard 병행)
3. `is_duplicate_in_db()` — 시트 기존 제목 대비 (`[시트중복]` 로그)
4. `is_duplicate_in_db()` — 같은 배치 내 수집 제목 대비 (`[배치중복]` 로그)
5. `is_news_excluded()` — 카테고리별 제외 키워드 매칭

**시트 저장 직전 최종 중복 제거**: `rows_to_save`를 시트에 쓰기 전 URL + 제목 유사도(80%) + 핵심단어 3개 겹침으로 최종 검증.

**임계값** (`is_duplicate_in_db`, `check_duplicate_in_cache`):

| 판정 | 임계값 | 비고 |
|------|--------|------|
| 제목 유사도 (SequenceMatcher + Jaccard) | ≥0.20 | 둘 중 하나라도 초과 시 중복 |
| 핵심 키워드 겹침 | ≥0.25 | `extract_key_phrases()` (1글자+ 단어, bigram, trigram) |
| 핵심 단어(2글자+) 3개 겹침 | 무조건 중복 | 제목 내 핵심 명사 교집합 |
| 본문 유사도 | ≥0.25 | 앞 500자 비교 (is_duplicate_in_db만) |
| 고유명사 주제 | `is_same_topic()` | 2글자+ 인물명 1개 또는 핵심단어 교집합 50%+ |

**URL 정규화**: `normalize_url()` — tracking 파라미터(utm_, ref, fbclid 등) 제거 후 비교. `load_existing_news()`에서도 기존 링크를 정규화하여 저장.

**재검색 루프** (`MAX_ROUNDS = 3`): 중복 제외로 카테고리 목표 미달 시 최대 3라운드 재검색. 라운드마다 `display` 수를 증가시켜 (`search_count * (round_num + 1)`, max 100) 더 많은 결과에서 비중복 뉴스를 찾음. 키워드 순서도 라운드마다 셔플.

**인물 제한**: `MAX_PERSON_NEWS = 3` — 같은 인물 뉴스는 배치당 최대 3건. NER로 인물명 추출, `person_counter`로 추적.

**당일 뉴스 필터링**: `is_today_news(pubDate)` — Naver API pubDate를 KST로 변환해 당일 여부 확인. `is_today_content(text)` — 본문 앞 300자에서 `N일` 패턴을 찾아 과거 사건 보도 필터링 (예: 오늘 발행됐지만 "14일 방송된" 기사 제외). `format_pub_date(pubDate)` — `'Sun, 15 Mar 2026 10:30:00 +0900'` → `'260315_10:30'` 변환, E열에 저장.

## Naver API Gotcha

Naver returns `description` not `content`. `api.js::saveNews()` maps `item.description → content`. Pydantic `NewsSaveItem` only accepts `content`.

## Required Files (not in git)

- `credentials.json` — Google Service Account key
- `config/dashboard_config.json` — runtime config (contains credentials, excluded from git)
- `config/users.json` — user accounts (excluded from git)
- `.env` — copy from `.env.example`

## Production Services (systemd)

```bash
# API 서버 (자동 재시작, 부팅 시 자동 시작)
systemctl status tynewsauto
systemctl restart tynewsauto
journalctl -u tynewsauto -f

# Cloudflare Tunnel (자동 재시작)
systemctl status cloudflared
systemctl restart cloudflared
journalctl -u cloudflared --no-pager | grep trycloudflare   # Quick Tunnel URL 확인
```

서비스 파일: `/etc/systemd/system/tynewsauto.service`, `/etc/systemd/system/cloudflared.service`
헬스체크 스크립트: `deploy/check-tunnel.sh` (cron 5분 주기 권장)

## Deployment

- **Docker**: `python:3.11-slim`, port 8080, `entrypoint.sh` decodes `GOOGLE_CREDENTIALS_BASE64`
- **DigitalOcean**: `.do/app.yaml`, `professional-s` instance
- **Production server**: SSH `root@129.212.236.253`, project at `/root/tynewsauto`, managed by systemd (`systemctl restart tynewsauto`). Deploy: `git pull && systemctl restart tynewsauto`. Server timezone: `Asia/Seoul`.

### Cloudflare Tunnel

`deploy/` 폴더에 설정 파일 포함. Quick Tunnel(현재)은 재시작 시 URL 변경됨. 고정 URL 필요 시 Named Tunnel 전환:

```bash
bash deploy/setup-tunnel.sh quick   # Quick Tunnel (임시 URL)
bash deploy/setup-tunnel.sh named   # Named Tunnel (고정 URL, Cloudflare 로그인 필요)
```
