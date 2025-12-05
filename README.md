# 뉴스 자동화 시스템

네이버 뉴스를 수집하여 구글 시트에 저장하고, 뉴스타운에 자동으로 업로드하는 시스템입니다.

## 새 컴퓨터 설치 가이드

### 1단계: Python 설치

1. [Python 공식 사이트](https://www.python.org/downloads/)에서 Python 3.10 이상 설치
2. 설치 시 **"Add Python to PATH"** 체크 필수

```bash
# 설치 확인
python --version
```

### 2단계: 프로젝트 다운로드

```bash
# 프로젝트 폴더로 이동
cd 원하는경로

# 또는 git clone (저장소가 있다면)
git clone <repository-url>
```

### 3단계: Python 패키지 설치

```bash
cd 자동화
pip install -r requirements.txt
```

### 4단계: Google Service Account 설정 (필수)

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **API 및 서비스** > **라이브러리**에서 다음 API 활성화:
   - Google Sheets API
   - Google Drive API
4. **API 및 서비스** > **사용자 인증 정보** > **서비스 계정 만들기**
5. 서비스 계정 생성 후 **키** 탭에서 **키 추가** > **새 키 만들기** > **JSON**
6. 다운로드된 JSON 파일을 `credentials.json`으로 이름 변경
7. `credentials.json`을 프로젝트 폴더에 복사
8. 서비스 계정 이메일(예: `xxx@project.iam.gserviceaccount.com`)을 구글 시트에 **편집자**로 공유

### 5단계: 네이버 API 설정

1. [네이버 개발자 센터](https://developers.naver.com/) 접속
2. **애플리케이션 등록**
3. **검색** API 사용 신청
4. Client ID와 Client Secret 복사

### 6단계: 환경 변수 설정 (.env)

`.env.example` 파일을 `.env`로 복사한 후 실제 값을 입력하세요:

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

`.env` 파일을 열어 아래 정보를 입력:

```env
# Google Sheets URL
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

# 뉴스타운 로그인 정보
NEWSTOWN_ID=your_id
NEWSTOWN_PW=your_password

# 네이버 API
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

> **참고**: `.env` 파일은 민감한 정보를 포함하므로 git에 커밋되지 않습니다.
> 대시보드 UI에서도 설정을 변경할 수 있습니다.

### 7단계: Chrome 브라우저 설치

업로드 기능은 Selenium을 사용하므로 Chrome 브라우저가 필요합니다.
- [Chrome 다운로드](https://www.google.com/chrome/)
- ChromeDriver는 `webdriver-manager`가 자동 관리

---

## 실행 방법

### 대시보드 (권장)

```bash
streamlit run dashboard.py
```

브라우저에서 자동으로 열리며, GUI로 모든 기능을 제어할 수 있습니다.

**대시보드 기능:**
- 뉴스 수집 시작/중지
- 업로드 감시 시작/중지
- 완료행 자동 삭제
- 키워드 및 설정 관리

### 개별 스크립트 실행

```bash
# 뉴스 수집
python naver_to_sheet.py

# 자동 업로드 (감시 모드)
python 뉴스타운_자동업로드_감시.py

# 완료행 삭제
python 뉴스타운_완료행_삭제.py
```

### Flask 서버 (Make.com 연동)

```bash
# 터미널 1: Flask 서버
python 서버용_업로드.py

# 터미널 2: ngrok 터널
python ngrok_간단실행.py
```

---

## 파일 구조

```
자동화/
├── dashboard.py              # Streamlit 대시보드 (메인 GUI)
├── naver_to_sheet.py         # 뉴스 수집 스크립트
├── 뉴스타운_자동업로드_감시.py  # 업로드 감시 스크립트
├── 뉴스타운_완료행_삭제.py     # 완료행 삭제 스크립트
├── 서버용_업로드.py           # Flask 웹서버
├── ngrok_간단실행.py          # ngrok 터널
├── .env                      # 환경 변수 (민감 정보, git 제외)
├── .env.example              # 환경 변수 템플릿
├── credentials.json          # 구글 서비스 계정 (직접 생성 필요)
├── requirements.txt          # Python 패키지 목록
├── .gitignore                # git 제외 파일 목록
├── config/
│   └── dashboard_config.json # 설정 파일 (자동 생성)
├── scripts/
│   ├── run_news_collection.py   # 뉴스 수집 래퍼
│   ├── run_upload_monitor.py    # 업로드 감시 래퍼
│   └── run_row_deletion.py      # 행 삭제 래퍼
└── utils/
    ├── config_manager.py     # 설정 관리 (.env 연동)
    └── process_manager.py    # 프로세스 관리
```

---

## 구글 시트 구조

| 열 | 내용 | 설명 |
|---|---|---|
| A | 제목 | 원본 뉴스 제목 |
| B | 본문 | 원본 뉴스 본문 |
| C | 링크 | 뉴스 링크 |
| D | 카테고리 | 연애/경제/스포츠 |
| E | AI_제목 | Make.com에서 생성 |
| F | AI_본문 | Make.com에서 생성 |
| G | 체크박스 | (사용 안 함) |
| H | 상태 | 완료/실패 표시 |

---

## 카테고리별 키워드 시스템

각 카테고리는 **Core(핵심)** 키워드와 **General(일반)** 키워드로 구분됩니다:

| 카테고리 | Core 키워드 예시 | General 키워드 예시 |
|---------|----------------|-------------------|
| 연애 | 연애, 열애, 결혼, 이혼 | 신랑, 웨딩, 커플링 |
| 경제 | 금리, 주식, 환율, GDP | 은행, 투자, ETF |
| 스포츠 | 야구, 축구, 올림픽 | 선수, 감독, 이적 |

대시보드에서 키워드를 자유롭게 추가/삭제할 수 있습니다.

---

## 트러블슈팅

### credentials.json 오류
```
gspread.exceptions.SpreadsheetNotFound
```
- 서비스 계정 이메일을 구글 시트에 **편집자**로 공유했는지 확인

### Chrome 오류
```
selenium.common.exceptions.WebDriverException
```
- Chrome 브라우저가 설치되어 있는지 확인
- 인터넷 연결 상태 확인 (ChromeDriver 자동 다운로드)

### 네이버 API 오류
```
401 Unauthorized
```
- Client ID/Secret이 올바른지 확인
- 검색 API가 활성화되어 있는지 확인

### 포트 사용 중 오류 (Flask)
```
Address already in use
```
- 기존 서버 프로세스 종료 후 재시작

---

## 주요 기능

1. **다양한 분야 뉴스 수집**: 연애/경제/스포츠 등 다양한 분야
2. **중복 방지**: 링크 + 제목 유사도로 중복 체크
3. **특정 인물 필터링**: 같은 인물 관련 뉴스는 최대 3개로 제한
4. **자동 카테고리 분류**: Core/General 키워드 기반 분류
5. **카테고리별 섹션 선택**: D열 값에 따라 뉴스타운 2차 섹션 자동 선택
6. **GUI 대시보드**: 모든 기능을 웹 인터페이스로 제어

---

## 필수 파일 체크리스트

다른 컴퓨터에서 실행하려면 다음이 필요합니다:

**필수 설정:**

- [ ] Python 3.10+ 설치
- [ ] Chrome 브라우저 설치
- [ ] `pip install -r requirements.txt` 실행
- [ ] `credentials.json` - Google Service Account 키 생성
- [ ] `.env` 파일 설정 (`.env.example` 복사 후 수정)

**자동 생성되는 파일:**

- `config/dashboard_config.json` - 최초 실행 시 자동 생성

**환경 변수 (.env) 항목:**

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `GOOGLE_SHEET_URL` | 구글 시트 URL | O |
| `NEWSTOWN_ID` | 뉴스타운 아이디 | O |
| `NEWSTOWN_PW` | 뉴스타운 비밀번호 | O |
| `NAVER_CLIENT_ID` | 네이버 API Client ID | O |
| `NAVER_CLIENT_SECRET` | 네이버 API Client Secret | O |
| `NEWS_DISPLAY_COUNT` | 뉴스 수집 개수 (기본: 30) | - |
| `UPLOAD_CHECK_INTERVAL` | 업로드 체크 간격 초 (기본: 30) | - |
| `DELETE_INTERVAL` | 삭제 간격 분 (기본: 60) | - |

---

## 라이선스

이 프로젝트는 개인용 자동화 도구입니다.
