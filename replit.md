# 뉴스 자동화 대시보드

## 프로젝트 개요
네이버 뉴스를 수집하여 구글 시트에 저장하고, 뉴스타운에 자동으로 업로드하는 시스템입니다. Streamlit 기반의 GUI 대시보드로 모든 기능을 통합 관리합니다.

## 주요 기능
- **뉴스 수집**: 네이버 뉴스 API를 통해 카테고리별 뉴스 수집
- **업로드 감시**: 구글 시트의 뉴스를 뉴스타운에 자동 업로드
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
├── 뉴스타운_자동업로드_감시.py  # 업로드 감시 스크립트
├── 뉴스타운_완료행_삭제.py     # 완료행 삭제 스크립트
├── 서버용_업로드.py           # Flask 웹서버
├── config/
│   └── dashboard_config.json # 설정 파일 (자동 생성)
├── scripts/
│   ├── run_news_collection.py
│   ├── run_upload_monitor.py
│   └── run_row_deletion.py
└── utils/
    ├── config_manager.py     # 설정 관리
    └── process_manager.py    # 프로세스 관리
```

## 필수 설정
다음 환경 변수 또는 설정이 필요합니다:
- `GOOGLE_SHEET_URL`: 구글 시트 URL
- `NEWSTOWN_ID`: 뉴스타운 로그인 ID
- `NEWSTOWN_PW`: 뉴스타운 비밀번호
- `NAVER_CLIENT_ID`: 네이버 API Client ID
- `NAVER_CLIENT_SECRET`: 네이버 API Client Secret
- `credentials.json`: 구글 서비스 계정 키 파일

## 카테고리 시스템
- **연애**: 연애, 열애, 결혼, 이혼 등
- **경제**: 금리, 주식, 환율, GDP 등
- **스포츠**: 야구, 축구, 올림픽 등

## 최근 변경사항
- 2024-12: Replit 환경 설정 완료
- Streamlit 포트 5000으로 설정
- 프록시 호스트 설정 적용

## 기술 스택
- Python 3.11
- Streamlit (대시보드)
- Selenium (웹 자동화)
- gspread (구글 시트 연동)
- Flask (웹훅 서버)
