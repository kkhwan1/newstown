# 뉴스 자동화 대시보드

## 프로젝트 개요
네이버 뉴스를 수집하여 PostgreSQL 데이터베이스와 구글 시트에 저장하고, 뉴스타운에 자동으로 업로드하는 시스템입니다. Streamlit 기반의 GUI 대시보드로 모든 기능을 통합 관리합니다.

## 주요 기능
- **뉴스 수집**: 네이버 뉴스 API를 통해 카테고리별 뉴스 수집 (DB + 구글시트 동시 저장)
- **뉴스 조회**: 수집된 뉴스 목록을 카테고리/상태별로 조회
- **프롬프트 관리**: AI 뉴스 가공을 위한 프롬프트 관리
- **업로드 감시**: 구글 시트의 뉴스를 Selenium으로 뉴스타운에 자동 업로드
- **완료행 삭제**: 업로드 완료된 행 자동 삭제
- **키워드 관리**: 카테고리별 Core/General 키워드 관리

## 실행 방법
Streamlit 대시보드가 포트 5000에서 실행됩니다:
```bash
streamlit run dashboard.py
```

## 프로젝트 구조
```
├── dashboard.py              # Streamlit 대시보드 (메인 GUI)
├── naver_to_sheet.py         # 뉴스 수집 스크립트
├── 뉴스타운_자동업로드_감시.py  # 업로드 감시 스크립트 (Selenium)
├── 뉴스타운_완료행_삭제.py     # 완료행 삭제 스크립트
├── config/
│   └── dashboard_config.json # 설정 파일 (자동 생성)
├── scripts/
│   ├── run_news_collection.py
│   ├── run_upload_monitor.py
│   └── run_row_deletion.py
└── utils/
    ├── config_manager.py     # 설정 관리
    ├── process_manager.py    # 프로세스 관리
    └── database.py           # PostgreSQL 데이터베이스 유틸리티
```

## 데이터베이스 테이블
### news 테이블
- id, title, content, link, category, source
- ai_title, ai_content (AI 가공 결과)
- status (pending/uploaded/failed)
- created_at, uploaded_at

### prompts 테이블
- id, name, category, prompt_text
- is_active, created_at, updated_at

## 필수 설정
- `DATABASE_URL`: PostgreSQL 연결 URL (자동 설정)
- `GOOGLE_SHEET_URL`: 구글 시트 URL
- `NEWSTOWN_ID/PW`: 뉴스타운 로그인 정보
- `NAVER_CLIENT_ID/SECRET`: 네이버 API 키
- `credentials.json`: 구글 서비스 계정 키 파일

## 페이지 구성
1. **대시보드**: 프로세스 상태 및 제어, 키워드 설정
2. **뉴스 조회**: 수집된 뉴스 목록 조회 (카테고리/상태 필터)
3. **프롬프트 관리**: AI 가공용 프롬프트 CRUD
4. **설정**: API 키, 로그인 정보 등 설정

## 카테고리 시스템
- **연애**: 연애, 열애, 결혼, 이혼 등
- **경제**: 금리, 주식, 환율, GDP 등
- **스포츠**: 야구, 축구, 올림픽 등

## 최근 변경사항
- 2024-12: PostgreSQL 데이터베이스 연동
- 2024-12: 페이지 기반 네비게이션 (사이드바)
- 2024-12: 프롬프트 관리 페이지 추가
- 2024-12: 뉴스 조회 페이지 추가
- 2024-12: UI 간소화 (세로 길이 축소)

## 기술 스택
- Python 3.11
- Streamlit (대시보드)
- PostgreSQL (psycopg2-binary)
- Selenium (웹 자동화)
- gspread (구글 시트 연동)
