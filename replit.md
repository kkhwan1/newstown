# 뉴스 자동화 대시보드

## 프로젝트 개요
네이버 뉴스를 수집하여 PostgreSQL 데이터베이스와 구글 시트에 저장하고, 뉴스타운에 자동으로 업로드하는 시스템입니다. Streamlit 기반 GUI 대시보드로 모든 기능을 통합 관리합니다.

## 주요 기능
- **뉴스 수집**: 네이버 뉴스 API로 카테고리별 뉴스 수집 (DB + 구글시트 동시 저장)
- **키워드 검색**: 수동으로 뉴스 검색 후 선택하여 저장
- **뉴스 조회**: DB/시트 저장 뉴스와 뉴스타운 업로드 뉴스 구분 표시
- **프롬프트 관리**: AI 뉴스 가공용 프롬프트 관리
- **업로드 감시**: Selenium으로 뉴스타운 자동 업로드
- **완료행 삭제**: 업로드 완료된 행 자동 삭제
- **키워드 관리**: 개별 삭제 가능한 Core/General 키워드 관리

## 실행 방법
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
│   ├── dashboard_config.json # 대시보드 설정
│   └── naver_api.json        # 네이버 API 키 (별도 보관)
├── scripts/
│   ├── run_news_collection.py
│   ├── run_upload_monitor.py
│   └── run_row_deletion.py
└── utils/
    ├── config_manager.py
    ├── process_manager.py
    └── database.py
```

## 데이터베이스 테이블
### news
- id, title, content, link
- **category**: 대분류 카테고리 (연애/경제/스포츠)
- **search_keyword**: 검색에 사용된 키워드 (예: 손흥민, 결혼, 주식)
- source, ai_title, ai_content (AI 가공 결과)
- status: pending (대기) / uploaded (뉴스타운 업로드 완료) / failed
- created_at, uploaded_at

### prompts
- id, name, category, prompt_text, is_active

## 필수 설정
- `DATABASE_URL`: PostgreSQL 연결 (자동)
- `config/naver_api.json`: 네이버 API 키
- `credentials.json`: 구글 서비스 계정 키
- 대시보드 설정 페이지에서: 구글 시트 URL, 뉴스타운 로그인 정보

## 페이지 구성
1. **대시보드**: 프로세스 제어, 키워드 설정
2. **키워드 검색**: 수동 뉴스 검색 및 저장 (최신순/인기순)
3. **뉴스 조회**: DB/시트 저장됨 | 뉴스타운 업로드됨 탭 구분
4. **프롬프트**: AI 가공용 프롬프트 관리
5. **설정**: API, 로그인, 간격 설정

## UI 특징
- 깔끔한 흑백 미니멀 디자인
- 작은 글자 크기로 정보 밀도 향상
- 표(DataFrame) 형태로 데이터 표시
- 키워드 개별 삭제 기능

## 최근 변경사항
- 2024-12-06: ProcessManager 파일 기반 상태 저장 (/tmp/process_status.json) - 세션 간 프로세스 추적 유지
- 2024-12-06: 실행 로그 영역 추가 - 프로세스 실행 상태 실시간 확인
- 2024-12-06: 카테고리 불일치 스킵 제거 (SKIP_MISMATCHED_CATEGORY=False) - 검색 키워드 기반 카테고리 할당
- 2024-12-06: 정렬 옵션 지원 (SORT_OPTION) - 인기순(sim) / 최신순(date) 선택 가능
- 2024-12-06: 중복 방지 3중 체크 - DB링크 + 시트링크 + 제목유사도(75%)
- 2024-12: 흑백 미니멀 UI 적용
- 2024-12: 네이버 API 별도 설정 파일 분리
- 2024-12: 뉴스 조회 탭 분리 (DB/시트 vs 뉴스타운)
- 2024-12: 키워드 검색 페이지 추가

## 중복 방지 로직
1. **링크 중복 체크**: DB와 시트의 기존 링크와 비교
2. **정규화 제목 체크**: 제목 정규화 후 완전 일치 비교
3. **유사도 75% 체크**: 제목 유사도 0.75 이상이면 중복 처리

## 카테고리 키워드 구조
```json
{
  "연애": {
    "core": ["연애", "열애", "결혼", ...],  // 검색에 사용
    "general": ["신랑", "신부", ...]        // 분류에 사용
  },
  "경제": {...},
  "스포츠": {...}
}
```

## 기술 스택
- Python 3.11
- Streamlit (대시보드)
- PostgreSQL (psycopg2-binary)
- Selenium (웹 자동화)
- gspread (구글 시트 연동)
- pandas (데이터 표시)
