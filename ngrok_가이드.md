# ngrok 사용 가이드

## 📋 기본 정보

- **도메인**: `news.ngrok.app`
- **인증 토큰**: 설정 완료 ✅
- **로컬 포트**: `80`

## 🚀 빠른 시작

### 방법 1: 간단 실행 스크립트 (권장)

```powershell
python ngrok_간단실행.py
```

### 방법 2: 배치 파일 실행

```powershell
.\ngrok_실행.bat
```

### 방법 3: 직접 명령어 실행

```powershell
.\ngrok.exe http 80 --domain=news.ngrok.app
```

## 🌐 접속 정보

### 외부 접속 URL
```
https://news.ngrok.app
```

### 로컬 접속 URL
```
http://127.0.0.1:80
http://localhost:80
```

## 📝 실행 순서

1. **로컬 서버 실행** (PowerShell 창 1)
   - 포트 80에서 서버가 실행 중이어야 합니다
   - 서버 코드를 실행하세요

2. **ngrok 터널 시작** (PowerShell 창 2)
   ```powershell
   python ngrok_간단실행.py
   ```
   또는
   ```powershell
   .\ngrok.exe http 80 --domain=news.ngrok.app
   ```

3. **접속 확인**
   - 외부에서 `https://news.ngrok.app` 접속
   - 또는 브라우저에서 접속 테스트

## 🔧 여러 포트 사용하기

여러 포트를 동시에 터널링하려면 각 포트마다 별도의 PowerShell 창에서 실행:

```powershell
# 창 1: 포트 80
.\ngrok.exe http 80 --domain=news.ngrok.app

# 창 2: 포트 8080 (랜덤 URL)
.\ngrok.exe http 8080

# 창 3: 포트 3000 (랜덤 URL)
.\ngrok.exe http 3000
```

각 터널은 고유한 URL을 가집니다.

## ⚠️ 주의사항

1. **ngrok 프로세스 종료 금지**
   - ngrok 프로세스를 종료하면 외부 접속이 불가능합니다
   - 터널을 계속 유지하려면 ngrok을 실행 상태로 유지하세요

2. **로컬 서버도 실행 필요**
   - 포트 80에서 로컬 서버가 실행 중이어야 합니다
   - 서버를 종료하면 외부 접속이 불가능합니다

3. **동시 실행**
   - 로컬 서버와 ngrok을 각각 다른 PowerShell 창에서 실행
   - 둘 다 실행 중이어야 정상 작동

## 🔍 문제 해결

### ngrok을 찾을 수 없음

```
❌ ngrok을 찾을 수 없습니다.
```

**해결**:
- `ngrok.exe`가 현재 폴더에 있는지 확인
- 또는 PATH에 ngrok 추가
- 또는 전체 경로로 실행

### 도메인 사용 불가

```
Error: domain "news.ngrok.app" not found
```

**해결**:
1. ngrok Edge 설정 확인
2. 또는 도메인 없이 실행:
   ```powershell
   .\ngrok.exe http 80
   ```
   (랜덤 URL이 생성됩니다)

### 포트 80이 열려있지 않음

**해결**:
- 포트 80에서 서버가 실행 중인지 확인
- 다른 프로그램이 포트 80을 사용 중인지 확인

## 📊 ngrok 웹 인터페이스

ngrok을 실행하면 웹 인터페이스도 제공됩니다:
- http://127.0.0.1:4040

여기서:
- 요청 로그 확인
- 요청/응답 내용 확인
- 터널 상태 확인

## ✅ 체크리스트

- [x] ngrok 설치 완료
- [x] 인증 토큰 설정 완료
- [ ] 로컬 서버 실행 중 (포트 80)
- [ ] ngrok 터널 시작
- [ ] 외부 접속 테스트 성공

## 🎯 최종 목표

외부에서 다음 주소로 접속 가능:
- `https://news.ngrok.app`

내부에서는:
- `http://localhost:80`
- `http://127.0.0.1:80`

두 주소 모두 같은 서버를 가리킵니다!

## 📞 추가 도움말

- ngrok 공식 문서: https://ngrok.com/docs
- 대시보드: https://dashboard.ngrok.com

