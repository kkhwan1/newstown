# -*- coding: utf-8 -*-
"""
완료행 삭제 래퍼 스크립트
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
    _shutdown_event.set()

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

def run_deletion(config):
    """완료행 삭제 실행"""
    global _shutdown_requested

    # 설정값 추출
    sheet_url = config.get('sheet_url', '')
    delete_interval = config.get('delete_interval', 60)  # 분 단위
    max_delete_count = config.get('max_delete_count', 10)
    completed_column = config.get('completed_column', 8)

    print(f"📝 설정:")
    print(f"   - 시트 URL: {sheet_url[:50]}...")
    print(f"   - 삭제 간격: {delete_interval}분")
    print(f"   - 최대 삭제 개수: {max_delete_count}")
    print(f"   - 완료 표시 열: {completed_column}")

    # 기존 모듈 import 및 설정 오버라이드
    import importlib.util
    module_path = os.path.join(parent_dir, '뉴스타운_완료행_삭제.py')

    spec = importlib.util.spec_from_file_location("row_deletion", module_path)
    deletion_module = importlib.util.module_from_spec(spec)

    # 설정 오버라이드
    deletion_module.SHEET_URL = sheet_url
    deletion_module.DELETE_INTERVAL = delete_interval
    deletion_module.MAX_DELETE_COUNT = max_delete_count
    deletion_module.COMPLETED_COLUMN = completed_column

    spec.loader.exec_module(deletion_module)

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
        doc = deletion_module.retry_with_backoff(client.open_by_url, sheet_url)
        sheet = doc.sheet1
        print("✅ 시트 연결 성공")
        print(f"\n👀 H열(완료 표시 열)을 감시 중...")
        print(f"   {delete_interval}분마다 완료된 행을 자동으로 삭제합니다.")
        print(f"   한 번에 최대 {max_delete_count}개 행만 삭제합니다.\n")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    delete_count = 0
    wait_seconds = delete_interval * 60

    # 삭제 루프 (인터럽트 가능)
    while not _shutdown_requested:
        try:
            delete_count += 1
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {delete_count}번째 삭제 작업 시작...")

            deleted_rows = deletion_module.delete_completed_rows(sheet)

            if deleted_rows > 0:
                print(f"   ✅ 총 {deleted_rows}개 행이 삭제되었습니다.")
            else:
                print(f"   ⏸️ 삭제할 완료된 행이 없습니다.")

            print(f"   다음 삭제 작업까지 {delete_interval}분({wait_seconds}초) 대기...")

            # 인터럽트 가능한 sleep
            if interruptible_sleep(wait_seconds):
                print("⚠️ 대기 중 종료 신호 수신")
                break

        except gspread.exceptions.APIError as e:
            error_code = e.response.status_code if hasattr(e, 'response') else None
            if error_code == 429 or "429" in str(e):
                print(f"⚠️ API 할당량 초과 - 60초 대기 후 재시도...")
                if interruptible_sleep(60):
                    break
                try:
                    doc = deletion_module.retry_with_backoff(client.open_by_url, sheet_url)
                    sheet = doc.sheet1
                    print("✅ 시트 재연결 성공")
                except Exception as reconnect_error:
                    print(f"⚠️ 시트 재연결 실패: {reconnect_error}")
                    if interruptible_sleep(wait_seconds):
                        break
            else:
                print(f"⚠️ API 오류 발생: {e}")
                if interruptible_sleep(wait_seconds):
                    break
        except Exception as e:
            print(f"⚠️ 오류 발생: {e}")
            if interruptible_sleep(wait_seconds):
                break

def main():
    """메인 실행 함수"""
    print("="*60)
    print("  완료행 삭제 러너 시작")
    print("="*60)

    setup_signal_handlers()

    config = load_config()
    print(f"📥 설정 로드됨: {json.dumps(config, ensure_ascii=False, indent=2)}")

    if _shutdown_requested:
        print("🛑 종료 요청으로 실행 취소")
        return

    try:
        run_deletion(config)
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("="*60)
        print("  완료행 삭제 러너 종료")
        print("="*60)

if __name__ == "__main__":
    main()
