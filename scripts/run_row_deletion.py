# -*- coding: utf-8 -*-
"""
완료행 삭제 래퍼 스크립트

대시보드에서 서브프로세스로 실행되며, 환경 변수로 설정을 받아 실행.
플랫폼별로 다른 완료 표시 열을 감시합니다.

지원 플랫폼:
- golftimes: M열(13번째) 감시

@TASK T8 - 플랫폼별 완료행 삭제 분리
@SPEC CLAUDE.md#Google-Sheets-Structure
"""
import sys
import os
import io
import json
import signal
import time
import threading
from typing import Optional

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
    add_log(msg, level=level, category="DELETION")

# 종료 플래그
_shutdown_requested = False
_shutdown_event = threading.Event()


# 플랫폼별 완료 열 (1-based)
# H열(8) = golftimes 완료, L열(12) = bizwnews 완료
COMPLETED_COLUMNS = [8, 12]  # 모든 열이 '완료'일 때만 행 삭제

# 플랫폼별 설정
PLATFORM_CONFIGS = {
    'golftimes': {
        'completed_column': 8,  # H열
        'display_name': '골프타임즈',
        'module_file': '완료행_삭제.py',
        'class_name': 'CompletedRowDeleter'
    }
}


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
    """환경 변수에서 설정 로드"""
    config_str = os.environ.get('PROCESS_CONFIG', '{}')
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        log("설정 파싱 실패, 기본값 사용", "WARN")
        return {}


def get_deleter_class(platform_name: str):
    """
    플랫폼에 해당하는 Deleter 클래스를 동적으로 로드

    Args:
        platform_name: 'golftimes'

    Returns:
        Deleter 클래스 또는 None
    """
    if platform_name not in PLATFORM_CONFIGS:
        log(f"지원하지 않는 플랫폼: {platform_name}", "ERROR")
        log(f"지원 플랫폼: {list(PLATFORM_CONFIGS.keys())}")
        return None

    config = PLATFORM_CONFIGS[platform_name]
    module_name = config['module_file'].replace('.py', '')
    class_name = config['class_name']

    # @SECURITY A01 - Path traversal protection (defense-in-depth)
    ALLOWED_MODULES = [
        '완료행_삭제.py',
    ]

    module_file = os.path.basename(config['module_file'])
    if module_file not in ALLOWED_MODULES:
        log(f"Error: 허용되지 않은 모듈 파일: {module_file}", "ERROR")
        log(f"허용된 모듈: {ALLOWED_MODULES}")
        return None

    try:
        # 모듈 로드
        import importlib.util
        module_path = os.path.join(parent_dir, module_file)

        # Verify resolved path is within the project directory
        resolved = os.path.realpath(module_path)
        if not resolved.startswith(os.path.realpath(parent_dir)):
            log("Error: 모듈 경로가 프로젝트 디렉토리 외부입니다", "ERROR")
            return None

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            log(f"모듈 로드 실패: {module_path}", "ERROR")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 클래스 가져오기
        deleter_class = getattr(module, class_name, None)
        if deleter_class is None:
            log(f"클래스를 찾을 수 없음: {class_name}", "ERROR")
            return None

        return deleter_class

    except Exception as e:
        log(f"모듈 로드 중 오류: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return None


def run_deletion(config):
    """완료행 삭제 실행"""
    global _shutdown_requested

    # 플랫폼 확인
    platform = config.get('platform', 'golftimes')
    if platform not in PLATFORM_CONFIGS:
        log(f"지원하지 않는 플랫폼: {platform}", "ERROR")
        return

    platform_config = PLATFORM_CONFIGS[platform]

    # 설정값 추출
    sheet_url = config.get('sheet_url', '')
    delete_interval = config.get('delete_interval', 60)
    max_delete_count = config.get('max_delete_count', 10)
    completed_columns = config.get('completed_columns', COMPLETED_COLUMNS)

    col_names = ', '.join(f"{chr(64 + c)}({c})" for c in completed_columns)
    log(f"설정: 시트 URL={sheet_url[:50]}..., 삭제 간격={delete_interval}분, 최대 삭제={max_delete_count}, 완료 열={col_names}")

    # Deleter 클래스 로드
    deleter_class = get_deleter_class(platform)
    if deleter_class is None:
        log("Deleter 클래스 로드 실패", "ERROR")
        return

    # Deleter 인스턴스 생성
    try:
        deleter = deleter_class(
            sheet_url=sheet_url,
            delete_interval=delete_interval,
            max_delete_count=max_delete_count,
            completed_columns=completed_columns
        )

        # 연결 확인
        if not deleter.connect():
            log("연결 실패", "ERROR")
            return

        log("연결 성공, 감시 시작", "SUCCESS")
        log(f"{col_names} 열 감시 중 (모두 완료 시 행 삭제), {delete_interval}분 간격, 최대 {max_delete_count}개")

    except Exception as e:
        log(f"초기화 실패: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return

    delete_count = 0
    wait_seconds = delete_interval * 60

    # 삭제 루프 (인터럽트 가능)
    while not _shutdown_requested:
        try:
            delete_count += 1
            log(f"[{delete_count}] 삭제 작업 시작...")

            deleted_rows = deleter.delete_completed_rows()

            if deleted_rows > 0:
                log(f"총 {deleted_rows}개 행 삭제 완료", "SUCCESS")
            else:
                log(f"삭제할 완료된 행 없음")

            log(f"다음 삭제까지 {delete_interval}분 대기...")

            # 인터럽트 가능한 sleep
            if interruptible_sleep(wait_seconds):
                log("대기 중 종료 신호 수신", "WARN")
                break

        except Exception as e:
            log(f"오류 발생: {e}", "ERROR")
            import traceback
            traceback.print_exc()

            # API 오류 후 잠시 대기 후 재시도
            if interruptible_sleep(60):
                break


def main():
    """메인 실행 함수"""
    log("완료행 삭제 러너 시작", "SUCCESS")

    setup_signal_handlers()

    config = load_config()
    safe_config = {k: v for k, v in config.items() if k not in ('site_pw', 'site_id', 'client_secret', 'client_id', 'naver_client_id', 'naver_client_secret')}
    log(f"설정 로드됨: {json.dumps(safe_config, ensure_ascii=False, indent=2)}")

    if _shutdown_requested:
        log("종료 요청으로 실행 취소", "WARN")
        return

    try:
        run_deletion(config)
    except KeyboardInterrupt:
        log("사용자에 의해 중단됨", "WARN")
    except Exception as e:
        log(f"오류 발생: {e}", "ERROR")
        import traceback
        traceback.print_exc()
    finally:
        log("완료행 삭제 러너 종료")


if __name__ == "__main__":
    main()
