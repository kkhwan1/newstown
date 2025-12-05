# -*- coding: utf-8 -*-
"""
업로드 감시 래퍼 스크립트
대시보드에서 서브프로세스로 실행되며, 환경 변수로 설정을 받아 실행
무한 루프를 인터럽트 가능하게 처리
"""
import sys
import os
import io
import json
import signal
import time
import threading

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 부모 디렉토리를 path에 추가
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# 종료 플래그
_shutdown_requested = False
_shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """신호 핸들러 - graceful shutdown"""
    global _shutdown_requested
    print(f"\n⚠️ 종료 신호 수신 (signal={signum}), 정리 중...")
    _shutdown_requested = True
    _shutdown_event.set()  # sleep 인터럽트

def setup_signal_handlers():
    """신호 핸들러 설정"""
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)
    else:
        signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def interruptible_sleep(seconds):
    """인터럽트 가능한 sleep"""
    return _shutdown_event.wait(timeout=seconds)

def load_config():
    """환경 변수에서 설정 로드"""
    config_str = os.environ.get('PROCESS_CONFIG', '{}')
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        print("⚠️ 설정 파싱 실패, 기본값 사용")
        return {}

def run_monitor(config):
    """업로드 감시 실행 (기존 스크립트 로직 래핑)"""
    global _shutdown_requested

    # 설정값 추출
    sheet_url = config.get('sheet_url', '')
    site_id = config.get('site_id', '')
    site_pw = config.get('site_pw', '')
    check_interval = config.get('check_interval', 30)
    completed_column = config.get('completed_column', 8)

    print(f"📝 설정:")
    print(f"   - 시트 URL: {sheet_url[:50]}...")
    print(f"   - 체크 간격: {check_interval}초")
    print(f"   - 완료 표시 열: {completed_column}")

    # 기존 모듈 import 및 설정 오버라이드
    import importlib.util
    module_path = os.path.join(parent_dir, '뉴스타운_자동업로드_감시.py')

    # 모듈 동적 로드
    spec = importlib.util.spec_from_file_location("upload_monitor", module_path)
    upload_module = importlib.util.module_from_spec(spec)

    # 설정 오버라이드
    upload_module.SHEET_URL = sheet_url
    upload_module.SITE_ID = site_id
    upload_module.SITE_PW = site_pw
    upload_module.CHECK_INTERVAL = check_interval
    upload_module.COMPLETED_COLUMN = completed_column

    spec.loader.exec_module(upload_module)

    # gspread 인증
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(parent_dir, 'credentials.json'), scope
        )
        client = gspread.authorize(creds)
        print("✅ 인증 성공")
    except FileNotFoundError:
        print("❌ 오류: 'credentials.json' 파일을 찾을 수 없습니다.")
        return
    except Exception as e:
        print(f"❌ 인증 오류: {e}")
        return

    # 시트 열기
    try:
        print("📡 시트 연결 시도 중...")
        doc = upload_module.retry_with_backoff(client.open_by_url, sheet_url)
        sheet = doc.sheet1
        print("✅ 시트 연결 성공")
        print("\n👀 E열(AI_제목)과 F열(AI_본문)을 감시 중...")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    check_count = 0

    # 감시 루프 (인터럽트 가능)
    while not _shutdown_requested:
        try:
            check_count += 1
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {check_count}번째 확인 중...")

            result = upload_module.check_and_upload(sheet)

            if result is None:
                print(f"   ⏸️ 업로드할 항목 없음")
            elif result:
                print(f"   ✅ 업로드 완료!")
            else:
                print(f"   ❌ 업로드 실패")

            print(f"   다음 확인까지 {check_interval}초 대기...")

            # 인터럽트 가능한 sleep
            if interruptible_sleep(check_interval):
                print("⚠️ 대기 중 종료 신호 수신")
                break

        except gspread.exceptions.APIError as e:
            error_code = e.response.status_code if hasattr(e, 'response') else None
            if error_code == 429 or "429" in str(e):
                print(f"⚠️ API 할당량 초과 - 60초 대기 후 재시도...")
                if interruptible_sleep(60):
                    break
                try:
                    doc = upload_module.retry_with_backoff(client.open_by_url, sheet_url)
                    sheet = doc.sheet1
                    print("✅ 시트 재연결 성공")
                except Exception as reconnect_error:
                    print(f"⚠️ 시트 재연결 실패: {reconnect_error}")
                    if interruptible_sleep(check_interval):
                        break
            else:
                print(f"⚠️ API 오류 발생: {e}")
                if interruptible_sleep(check_interval):
                    break
        except Exception as e:
            print(f"⚠️ 오류 발생: {e}")
            if interruptible_sleep(check_interval):
                break

def main():
    """메인 실행 함수"""
    print("="*60)
    print("  업로드 감시 러너 시작")
    print("="*60)

    setup_signal_handlers()

    config = load_config()
    print(f"📥 설정 로드됨: {json.dumps(config, ensure_ascii=False, indent=2)}")

    if _shutdown_requested:
        print("🛑 종료 요청으로 실행 취소")
        return

    try:
        run_monitor(config)
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("="*60)
        print("  업로드 감시 러너 종료")
        print("="*60)

if __name__ == "__main__":
    main()
