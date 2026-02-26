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

# 종료 플래그
_shutdown_requested = False
_shutdown_event = threading.Event()


# 플랫폼별 설정
PLATFORM_CONFIGS = {
    'golftimes': {
        'completed_column': 13,  # M열
        'display_name': '골프타임즈',
        'module_file': '완료행_삭제.py',
        'class_name': 'CompletedRowDeleter'
    }
}


def signal_handler(signum, frame):
    """신호 핸들러 - graceful shutdown"""
    global _shutdown_requested
    print(f"\n종료 신호 수신 (signal={signum}), 정리 중...")
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
        print("설정 파싱 실패, 기본값 사용")
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
        print(f"지원하지 않는 플랫폼: {platform_name}")
        print(f"지원 플랫폼: {list(PLATFORM_CONFIGS.keys())}")
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
        print(f"Error: 허용되지 않은 모듈 파일: {module_file}")
        print(f"허용된 모듈: {ALLOWED_MODULES}")
        return None

    try:
        # 모듈 로드
        import importlib.util
        module_path = os.path.join(parent_dir, module_file)

        # Verify resolved path is within the project directory
        resolved = os.path.realpath(module_path)
        if not resolved.startswith(os.path.realpath(parent_dir)):
            print(f"Error: 모듈 경로가 프로젝트 디렉토리 외부입니다")
            return None

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            print(f"모듈 로드 실패: {module_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 클래스 가져오기
        deleter_class = getattr(module, class_name, None)
        if deleter_class is None:
            print(f"클래스를 찾을 수 없음: {class_name}")
            return None

        return deleter_class

    except Exception as e:
        print(f"모듈 로드 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_deletion(config):
    """완료행 삭제 실행"""
    global _shutdown_requested

    # 플랫폼 확인
    platform = config.get('platform', 'golftimes')
    if platform not in PLATFORM_CONFIGS:
        print(f"지원하지 않는 플랫폼: {platform}")
        return

    platform_config = PLATFORM_CONFIGS[platform]

    # 설정값 추출
    sheet_url = config.get('sheet_url', '')
    delete_interval = config.get('delete_interval', 60)
    max_delete_count = config.get('max_delete_count', 10)
    completed_column = config.get('completed_column', platform_config['completed_column'])

    print(f"설정:")
    print(f"   - 플랫폼: {platform_config['display_name']}")
    print(f"   - 시트 URL: {sheet_url[:50]}...")
    print(f"   - 삭제 간격: {delete_interval}분")
    print(f"   - 최대 삭제 개수: {max_delete_count}")
    print(f"   - 완료 표시 열: {completed_column} ({chr(64 + completed_column)}열)")

    # Deleter 클래스 로드
    deleter_class = get_deleter_class(platform)
    if deleter_class is None:
        print("Deleter 클래스 로드 실패")
        return

    # Deleter 인스턴스 생성
    try:
        deleter = deleter_class(
            sheet_url=sheet_url,
            delete_interval=delete_interval,
            max_delete_count=max_delete_count,
            completed_column=completed_column
        )

        # 연결 확인
        if not deleter.connect():
            print("연결 실패")
            return

        print("연결 성공")
        print(f"\n{chr(64 + completed_column)}열({platform_config['display_name']} 완료 표시 열) 감시 중...")
        print(f"{delete_interval}분마다 완료된 행 자동 삭제")
        print(f"한 번에 최대 {max_delete_count}개 행만 삭제\n")

    except Exception as e:
        print(f"초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return

    delete_count = 0
    wait_seconds = delete_interval * 60

    # 삭제 루프 (인터럽트 가능)
    while not _shutdown_requested:
        try:
            delete_count += 1
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {delete_count}번째 삭제 작업 시작...")

            deleted_rows = deleter.delete_completed_rows()

            if deleted_rows > 0:
                print(f"   총 {deleted_rows}개 행 삭제 완료")
            else:
                print(f"   삭제할 완료된 행 없음")

            print(f"   다음 삭제 작업까지 {delete_interval}분({wait_seconds}초) 대기...")

            # 인터럽트 가능한 sleep
            if interruptible_sleep(wait_seconds):
                print("대기 중 종료 신호 수신")
                break

        except Exception as e:
            print(f"오류 발생: {e}")
            import traceback
            traceback.print_exc()

            # API 오류 후 잠시 대기 후 재시도
            if interruptible_sleep(60):
                break


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("  완료행 삭제 러너 시작")
    print("=" * 60)

    setup_signal_handlers()

    config = load_config()
    print(f"설정 로드됨: {json.dumps(config, ensure_ascii=False, indent=2)}")

    if _shutdown_requested:
        print("종료 요청으로 실행 취소")
        return

    try:
        run_deletion(config)
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("=" * 60)
        print("  완료행 삭제 러너 종료")
        print("=" * 60)


if __name__ == "__main__":
    main()
