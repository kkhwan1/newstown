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

from utils.logger import add_log

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")
    add_log(msg, level=level, category="UPLOAD")

# 종료 플래그
_shutdown_requested = False
_shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """신호 핸들러 - graceful shutdown"""
    global _shutdown_requested
    log(f"종료 신호 수신 (signal={signum}), 정리 중...", "WARN")
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
    """환경 변수 또는 DB에서 설정 로드"""
    config_str = os.environ.get('PROCESS_CONFIG', '{}')
    try:
        config = json.loads(config_str)
        if config.get('sheet_url'):
            return config
    except json.JSONDecodeError:
        pass
    
    log("환경변수에 설정 없음, DB에서 직접 로드", "INFO")
    try:
        import psycopg2
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            log("DATABASE_URL 없음", "ERROR")
            return {}
        
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        config = {}
        
        cur.execute("SELECT value FROM settings WHERE key = 'google_sheet'")
        r = cur.fetchone()
        if r: config['sheet_url'] = json.loads(r[0]).get('url', '')
        
        cur.execute("SELECT value FROM settings WHERE key = 'newstown'")
        r = cur.fetchone()
        if r:
            nt = json.loads(r[0])
            config['site_id'] = nt.get('site_id', '')
            config['site_pw'] = nt.get('site_pw', '')
        
        cur.execute("SELECT value FROM settings WHERE key = 'golftimes'")
        r = cur.fetchone()
        if r:
            gt = json.loads(r[0])
            config['golftimes_id'] = gt.get('site_id', 'thegolftimes')
            config['golftimes_pw'] = gt.get('site_pw', 'Golf1220')
        
        cur.execute("SELECT value FROM settings WHERE key = 'upload_monitor'")
        r = cur.fetchone()
        if r:
            um = json.loads(r[0])
            config['check_interval'] = um.get('check_interval', 30)
            config['concurrent_uploads'] = um.get('concurrent_uploads', 2)
        
        cur.execute("SELECT value FROM settings WHERE key = 'upload_platforms'")
        r = cur.fetchone()
        if r:
            config['platforms'] = json.loads(r[0])
        
        cur.close()
        conn.close()
        
        log(f"DB에서 설정 로드 완료: 시트={config.get('sheet_url', '')[:30]}...", "SUCCESS")
        return config
    except Exception as e:
        log(f"DB 설정 로드 실패: {e}", "ERROR")
        return {}

def run_monitor(config):
    """업로드 감시 실행 (기존 스크립트 로직 래핑)"""
    global _shutdown_requested

    sheet_url = config.get('sheet_url', '')
    site_id = config.get('site_id', '')
    site_pw = config.get('site_pw', '')
    check_interval = config.get('check_interval', 30)
    completed_column = config.get('completed_column', 8)
    concurrent_uploads = config.get('concurrent_uploads', 1)
    
    golftimes_id = config.get('golftimes_id', 'thegolftimes')
    golftimes_pw = config.get('golftimes_pw', 'Golf1220')
    
    platforms = config.get('platforms', {})
    newstown_enabled = platforms.get('newstown', {}).get('enabled', True)
    golftimes_enabled = platforms.get('golftimes', {}).get('enabled', False)

    log(f"설정: 체크 간격 {check_interval}초")
    log(f"뉴스타운: {'활성화' if newstown_enabled else '비활성화'}")
    log(f"골프타임즈: {'활성화' if golftimes_enabled else '비활성화'}")

    import importlib.util
    module_path = os.path.join(parent_dir, '뉴스타운_자동업로드_감시.py')

    spec = importlib.util.spec_from_file_location("upload_monitor", module_path)
    upload_module = importlib.util.module_from_spec(spec)
    
    spec.loader.exec_module(upload_module)
    
    upload_module.SHEET_URL = sheet_url
    upload_module.SITE_ID = site_id
    upload_module.SITE_PW = site_pw
    upload_module.CHECK_INTERVAL = check_interval
    upload_module.COMPLETED_COLUMN = completed_column
    upload_module.CONCURRENT_UPLOADS = concurrent_uploads
    
    upload_module.GOLFTIMES_ID = golftimes_id
    upload_module.GOLFTIMES_PW = golftimes_pw
    upload_module.NEWSTOWN_ENABLED = newstown_enabled
    upload_module.GOLFTIMES_ENABLED = golftimes_enabled

    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(parent_dir, 'credentials.json'), scope
        )
        client = gspread.authorize(creds)
        log("구글 시트 인증 성공", "SUCCESS")
    except FileNotFoundError:
        log("credentials.json 파일을 찾을 수 없습니다", "ERROR")
        return
    except Exception as e:
        log(f"인증 오류: {e}", "ERROR")
        return

    try:
        log("시트 연결 시도 중...")
        doc = upload_module.retry_with_backoff(client.open_by_url, sheet_url)
        sheet = doc.sheet1
        log("시트 연결 성공, 감시 시작", "SUCCESS")
    except Exception as e:
        log(f"시트 연결 실패: {e}", "ERROR")
        return

    check_count = 0

    while not _shutdown_requested:
        try:
            check_count += 1
            log(f"[{check_count}] 시트 확인 중...")

            if newstown_enabled:
                newstown_result = upload_module.check_and_upload(sheet)
                if newstown_result is None:
                    log(f"[{check_count}] [뉴스타운] 업로드할 항목 없음")
                elif newstown_result:
                    log(f"[{check_count}] [뉴스타운] 업로드 완료!", "SUCCESS")
                else:
                    log(f"[{check_count}] [뉴스타운] 업로드 실패", "WARN")

            if golftimes_enabled:
                golftimes_result = upload_module.check_and_upload_golftimes(sheet)
                if golftimes_result is None:
                    log(f"[{check_count}] [골프타임즈] 업로드할 항목 없음")
                elif golftimes_result:
                    log(f"[{check_count}] [골프타임즈] 업로드 완료!", "SUCCESS")
                else:
                    log(f"[{check_count}] [골프타임즈] 업로드 실패", "WARN")

            if interruptible_sleep(check_interval):
                log("대기 중 종료 신호 수신", "WARN")
                break

        except gspread.exceptions.APIError as e:
            error_code = e.response.status_code if hasattr(e, 'response') else None
            if error_code == 429 or "429" in str(e):
                log("API 할당량 초과 - 60초 대기 후 재시도...", "WARN")
                if interruptible_sleep(60):
                    break
                try:
                    doc = upload_module.retry_with_backoff(client.open_by_url, sheet_url)
                    sheet = doc.sheet1
                    log("시트 재연결 성공", "SUCCESS")
                except Exception as reconnect_error:
                    log(f"시트 재연결 실패: {reconnect_error}", "ERROR")
                    if interruptible_sleep(check_interval):
                        break
            else:
                log(f"API 오류 발생: {e}", "ERROR")
                if interruptible_sleep(check_interval):
                    break
        except Exception as e:
            error_msg = str(e)
            if "selenium" in error_msg.lower() or "webdriver" in error_msg.lower():
                log(f"Selenium 오류: {e} - 브라우저 재시작 필요할 수 있음", "ERROR")
            elif "timeout" in error_msg.lower():
                log(f"타임아웃 오류: {e} - 네트워크 상태 확인 필요", "ERROR")
            elif "connection" in error_msg.lower():
                log(f"연결 오류: {e} - 네트워크 연결 확인", "ERROR")
            else:
                log(f"오류 발생: {e}", "ERROR")
            if interruptible_sleep(check_interval):
                break

def main():
    """메인 실행 함수 - 자동 재시작 포함"""
    global _shutdown_requested
    
    log("뉴스타운 업로드 감시 시작", "SUCCESS")

    setup_signal_handlers()
    config = load_config()

    if _shutdown_requested:
        log("종료 요청으로 실행 취소", "WARN")
        return

    max_retries = 10
    retry_count = 0
    retry_delay = 60
    
    while not _shutdown_requested and retry_count < max_retries:
        try:
            run_monitor(config)
            if _shutdown_requested:
                break
            retry_count = 0
        except KeyboardInterrupt:
            log("사용자에 의해 중단됨", "WARN")
            break
        except Exception as e:
            retry_count += 1
            log(f"오류 발생 ({retry_count}/{max_retries}): {e}", "ERROR")
            import traceback
            traceback.print_exc()
            
            if retry_count < max_retries and not _shutdown_requested:
                log(f"{retry_delay}초 후 재시작 시도...", "WARN")
                if interruptible_sleep(retry_delay):
                    log("대기 중 종료 신호 수신", "WARN")
                    break
                log(f"업로드 감시 재시작 ({retry_count}/{max_retries})", "SUCCESS")
            else:
                log("최대 재시도 횟수 초과 또는 종료 요청, 프로세스 종료", "ERROR")
                break
    
    log("업로드 감시 프로세스 종료")

if __name__ == "__main__":
    main()
