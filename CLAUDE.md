# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean news automation system that collects news from Naver, stores in Google Sheets, and auto-uploads to Newstown via Selenium browser automation. Features a Streamlit-based GUI dashboard for easy management.

## Quick Start

### Dashboard (Recommended)

```bash
streamlit run dashboard.py
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Common Commands

### News Collection

```bash
python naver_to_sheet.py
```

### Auto-Upload (Monitoring Mode)

```bash
python 뉴스타운_자동업로드_감시.py
```

### Row Deletion

```bash
python 뉴스타운_완료행_삭제.py
```

### Flask Server + ngrok (Make.com Integration)

```bash
# Terminal 1: Start Flask webhook server
python 서버용_업로드.py

# Terminal 2: Start ngrok tunnel
python ngrok_간단실행.py
```

## Architecture

### Data Flow

1. `naver_to_sheet.py` → Naver News API → Google Sheets (columns A-D)
2. Make.com (external) → Processes A-D → Fills E/F columns (AI-generated title/content)
3. Upload scripts → Read E/F columns → Selenium → Newstown website

### Google Sheets Structure

| Column | Content | Source |
|--------|---------|--------|
| A | Original title | Naver API |
| B | Original content | Scraped |
| C | Link | Naver API |
| D | Category (연애/경제/스포츠) | Auto-classified |
| E | AI Title | Make.com |
| F | AI Content | Make.com |
| H | Upload status | Script |

### Project Structure

```text
자동화/
├── dashboard.py              # Streamlit Dashboard (Main GUI)
├── naver_to_sheet.py         # News collection
├── 뉴스타운_자동업로드_감시.py  # Upload monitoring
├── 뉴스타운_완료행_삭제.py     # Row deletion
├── 서버용_업로드.py           # Flask webhook server
├── credentials.json          # Google Service Account (required)
├── config/
│   └── dashboard_config.json # Configuration (auto-generated)
├── scripts/
│   ├── run_news_collection.py
│   ├── run_upload_monitor.py
│   └── run_row_deletion.py
└── utils/
    ├── config_manager.py     # JSON config management
    └── process_manager.py    # Subprocess lifecycle
```

### Key Components

- **ConfigManager** (`utils/config_manager.py`): JSON-based configuration persistence
- **ProcessManager** (`utils/process_manager.py`): Subprocess lifecycle management
- **Dashboard** (`dashboard.py`): Streamlit GUI for all functions
- **Wrapper Scripts** (`scripts/`): Environment variable-based config passing

## Configuration

### Config File Location

`config/dashboard_config.json` - auto-generated with defaults on first run

### Key Settings

```json
{
  "news_collection": {
    "keywords": {"연애": 15, "경제": 15, "스포츠": 15},
    "display_count": 30
  },
  "category_keywords": {
    "연애": {"core": [...], "general": [...]},
    "경제": {"core": [...], "general": [...]},
    "스포츠": {"core": [...], "general": [...]}
  },
  "google_sheet": {"url": "..."},
  "newstown": {"site_id": "...", "site_pw": "..."},
  "naver_api": {"client_id": "...", "client_secret": "..."}
}
```

## Required Files for New Installation

1. **credentials.json** - Google Service Account key (create manually)
2. **Chrome browser** - For Selenium automation
3. **Python 3.10+** - Runtime environment

### Setup Steps

1. Install Python 3.10+
2. Run `pip install -r requirements.txt`
3. Create Google Service Account and download `credentials.json`
4. Share Google Sheet with service account email
5. Get Naver API credentials from developers.naver.com
6. Run `streamlit run dashboard.py`

See README.md for detailed installation guide.

## External Dependencies

- **Make.com**: Workflow automation that fills E/F columns with AI-generated content
- **Newstown**: Target upload site (http://www.newstown.co.kr)
- **Naver News API**: Source for news collection
- **Google Sheets API**: Data storage
- **Google Drive API**: Sheet access

## Category Classification System

News articles are classified using a two-tier keyword system:

- **Core keywords**: High-priority terms that strongly indicate a category
- **General keywords**: Supporting terms for classification

The `KEYWORD_CATEGORY_MAP` in `naver_to_sheet.py` is dynamically generated from `category_keywords` in the config when run through the dashboard.
