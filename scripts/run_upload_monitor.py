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

# Windows 콘솔에서 UTF-8 인코딩 설정 (stdout이 유효한 경우만)
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer') and not sys.stdout.closed:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass
    if hasattr(sys.stderr, 'buffer') and not sys.stderr.closed:
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

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

def cleanup_chrome_processes():
    """남아있는 Chrome/Chromium 프로세스 정리"""
    import subprocess
    try:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/IM', 'chromedriver.exe', '/F'], capture_output=True, timeout=10)
            subprocess.run(['taskkill', '/IM', 'chrome.exe', '/F'], capture_output=True, timeout=10)
        else:
            subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=10)
            subprocess.run(['pkill', '-f', 'chromium'], capture_output=True, timeout=10)
            subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=10)
    except Exception:
        pass

def load_config():
    """환경 변수에서 설정 로드 (프론트엔드에서 전달)"""
    config_str = os.environ.get('PROCESS_CONFIG', '{}')
    try:
        config = json.loads(config_str)
        if config:
            return config
    except json.JSONDecodeError:
        log("환경변수 설정 파싱 실패", "ERROR")
        return {}

    return {}

def run_monitor(config):
    """업로드 감시 실행 (신규 플랫폼 시스템 사용)"""
    global _shutdown_requested

    sheet_url = config.get('sheet_url', '')
    if not sheet_url:
        try:
            from utils.config_manager import get_config_manager
            cm = get_config_manager()
            sheet_url = cm.get("google_sheet", "url") or ''
            if sheet_url:
                log("sheet_url을 ConfigManager에서 로드함", "SUCCESS")
        except Exception as e:
            log(f"sheet_url ConfigManager 로드 실패: {e}", "WARN")
    check_interval = config.get('check_interval', 30)
    completed_column = config.get('completed_column', 8)

    # Get selected platforms from frontend
    selected_platforms = config.get('selected_platforms', ['golftimes'])
    upload_platforms = config.get('upload_platforms', {})

    # Load credentials from ConfigManager if not in config
    # This handles the case where frontend sends minimal config
    credential_sections = set()
    for platform_id in selected_platforms:
        platform_cfg = upload_platforms.get(platform_id, {})
        cred_section = platform_cfg.get('credentials_section', platform_id)
        credential_sections.add(cred_section)

    # Load credentials from ConfigManager for each credential section
    # Also reload if section contains ***MASKED*** values (from frontend API masking)
    for section in credential_sections:
        section_data = config.get(section)
        needs_reload = (
            not section_data or
            any(v == '***MASKED***' for v in (section_data.values() if isinstance(section_data, dict) else []))
        )
        if needs_reload:
            try:
                from utils.config_manager import get_config_manager
                cm = get_config_manager()
                section_config = cm.get(section)
                if section_config:
                    config[section] = section_config
                    log(f"설정 로드됨: {section} 섹션", "SUCCESS")
            except Exception as e:
                log(f"{section} 섹션 설정 로드 실패: {e}", "WARN")

    # Filter enabled platforms from selected
    enabled_platforms = [
        p for p in selected_platforms
        if upload_platforms.get(p, {}).get('enabled', False)
    ]

    # Debug logging
    log(f"DEBUG: selected_platforms={selected_platforms}", "INFO")
    log(f"DEBUG: upload_platforms keys={list(upload_platforms.keys())}", "INFO")
    for p in selected_platforms:
        plat_cfg = upload_platforms.get(p, {})
        log(f"DEBUG: {p} enabled={plat_cfg.get('enabled', False)} config={plat_cfg}", "INFO")

    if not enabled_platforms:
        log("활성화된 플랫폼이 없습니다", "WARN")
        return

    log(f"설정: 체크 간격 {check_interval}초")
    log(f"활성화된 플랫폼: {', '.join(enabled_platforms)}")

    # Import platform system
    try:
        from utils.platforms import create_uploader, DriverPool
        from utils.platforms.base import UploadResult
    except ImportError as e:
        log(f"플랫폼 모듈 임포트 실패: {e}", "ERROR")
        return

    # Google Sheets 연결
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

    # 시트 연결 (재시도 로직 포함)
    def retry_with_backoff(func, *args, max_retries=3, base_delay=2, **kwargs):
        """지수 백오프로 재시도"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    log(f"재시도 ({attempt + 1}/{max_retries}) {delay}초 후...", "WARN")
                    if interruptible_sleep(delay):
                        return None
                else:
                    raise e
        return None

    try:
        log("시트 연결 시도 중...")
        doc = retry_with_backoff(client.open_by_url, sheet_url)
        if doc is None:
            log("시트 연결 취소됨", "WARN")
            return
        sheet = doc.sheet1
        log("시트 연결 성공, 감시 시작", "SUCCESS")
    except Exception as e:
        log(f"시트 연결 실패: {e}", "ERROR")
        return

    # Driver pool for reusing browser sessions
    driver_pool = DriverPool(max_size=1)

    try:
        check_count = 0

        while not _shutdown_requested:
            try:
                check_count += 1
                log(f"[{check_count}] 시트 확인 중...")

                # Get all data from sheet
                all_data = sheet.get_all_values()
                if not all_data:
                    log("시트에 데이터 없음")
                    if interruptible_sleep(check_interval):
                        break
                    continue

                header = all_data[0]

                # Find column indices
                title_col_idx = None
                content_col_idx = None
                status_col_idx = None
                link_col_idx = None

                for idx, col_name in enumerate(header):
                    col_lower = col_name.lower()
                    if '제목' in col_name or 'title' in col_lower:
                        title_col_idx = idx
                    elif '내용' in col_name or 'content' in col_lower or '본문' in col_name:
                        content_col_idx = idx
                    elif '완료' in col_name or 'status' in col_lower or '상태' in col_name:
                        status_col_idx = idx
                    elif '링크' in col_name or 'link' in col_lower:
                        link_col_idx = idx

                if title_col_idx is None or content_col_idx is None:
                    log(f"필수 컬럼을 찾을 수 없음 (제목/내용)", "WARN")
                    if interruptible_sleep(check_interval):
                        break
                    continue

                # Process each platform
                for platform_id in enabled_platforms:
                    try:
                        platform_config = upload_platforms.get(platform_id, {})

                        # Resolve credentials from credentials_section
                        # This connects upload_platforms.golftimes.credentials_section -> config.golftimes
                        credentials_section = platform_config.get('credentials_section', platform_id)
                        credentials_config = config.get(credentials_section, {})

                        # Prepare platform config with credentials for uploader
                        # Priority: config[credentials_section] > environment variables
                        platform_config_with_creds = {
                            **platform_config,
                            'golftimes_id': credentials_config.get('site_id') or os.environ.get('GOLFTIMES_ID', ''),
                            'golftimes_pw': credentials_config.get('site_pw') or os.environ.get('GOLFTIMES_PW', ''),
                            'headless': platform_config.get('headless', True),
                            'timeout': platform_config.get('timeout', 120),
                        }

                        # Get column mappings from platform config
                        title_col = platform_config.get('title_column', title_col_idx)
                        content_col = platform_config.get('content_column', content_col_idx)
                        status_col = platform_config.get('completed_column', status_col_idx)

                        # Validate credentials
                        if not platform_config_with_creds.get('golftimes_id') or not platform_config_with_creds.get('golftimes_pw'):
                            log(f"[{platform_id}] 자격증정이 설정되지 않았습니다 (credentials_section: {credentials_section})", "WARN")
                            continue

                        # Find rows ready for upload
                        rows_to_upload = []
                        row_indices = []

                        for row_idx, row in enumerate(all_data[1:], start=2):  # Skip header, 1-indexed
                            if len(row) <= max(title_col, content_col):
                                continue

                            title = row[title_col] if title_col < len(row) else ''
                            content = row[content_col] if content_col < len(row) else ''

                            # Check status column if exists
                            if status_col is not None and status_col < len(row):
                                status = str(row[status_col]).strip().lower()
                                if status in ['완료', 'completed', '업로드완료', '✓']:
                                    continue

                            if title and content:
                                rows_to_upload.append((title, content))
                                row_indices.append(row_idx)

                        if not rows_to_upload:
                            log(f"[{check_count}] [{platform_id}] 업로드할 항목 없음")
                            continue

                        log(f"[{check_count}] [{platform_id}] {len(rows_to_upload)}개 항목 업로드 시도...")

                        # Create uploader and upload (with resolved credentials)
                        with driver_pool.uploader(platform_id, platform_config_with_creds) as uploader:
                            # Login once per batch
                            if not uploader.is_logged_in:
                                if not uploader.login():
                                    log(f"[{platform_id}] 로그인 실패", "ERROR")
                                    continue
                                log(f"[{platform_id}] 로그인 성공", "SUCCESS")

                            # Upload each row
                            success_count = 0
                            for (title, content), row_idx in zip(rows_to_upload, row_indices):
                                if _shutdown_requested:
                                    break

                                try:
                                    result = uploader.upload(title, content, submit=True)
                                    if result.success:
                                        success_count += 1
                                        # Update status in sheet
                                        if status_col is not None:
                                            sheet.update_cell(row_idx, status_col + 1, '완료')
                                        log(f"[{platform_id}] '{title[:30]}...' 업로드 완료", "SUCCESS")
                                    else:
                                        log(f"[{platform_id}] '{title[:30]}...' 업로드 실패: {result.error_message}", "WARN")
                                except Exception as e:
                                    log(f"[{platform_id}] 업로드 중 오류: {e}", "ERROR")

                            if success_count > 0:
                                log(f"[{check_count}] [{platform_id}] {success_count}/{len(rows_to_upload)} 업로드 완료!", "SUCCESS")
                                # Small delay between uploads
                                time.sleep(2)

                    except Exception as e:
                        log(f"[{check_count}] [{platform_id}] 플랫폼 처리 오류: {e}", "ERROR")

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
                        doc = retry_with_backoff(client.open_by_url, sheet_url)
                        if doc is not None:
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
                    import traceback
                    traceback.print_exc()
                if interruptible_sleep(check_interval):
                    break

    finally:
        # Cleanup driver pool
        driver_pool.close_all()
        log("드라이버 풀 정리 완료")

def main():
    """메인 실행 함수 - 자동 재시작 포함"""
    global _shutdown_requested

    log("업로드 감시 시작", "SUCCESS")

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
