# -*- coding: utf-8 -*-
# @TASK P0-T0.2 - 뉴스 수집 래퍼 스크립트 (글로벌 변수 변이 제거)
# @SPEC docs/planning/
"""
뉴스 수집 래퍼 스크립트
대시보드에서 서브프로세스로 실행되며, 환경 변수로 설정을 받아 실행
글로벌 변수 변이를 제거하고 NewsCollectorConfig 객체를 사용합니다.
"""
import sys
import os
import io
import json
import signal

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

# 부모 디렉토리를 path에 추가 (naver_to_sheet.py import를 위해)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.logger import add_log


def log(msg, level="INFO"):
    try:
        print(f"[{level}] {msg}")
    except (ValueError, OSError):
        pass  # stdout이 닫힌 경우 무시
    add_log(msg, level=level, category="NEWS")


# 종료 플래그
_shutdown_requested = False


def signal_handler(signum, frame):
    """신호 핸들러 - graceful shutdown"""
    global _shutdown_requested
    log(f"종료 신호 수신 (signal={signum}), 정리 중...", "WARN")
    _shutdown_requested = True


def setup_signal_handlers():
    """신호 핸들러 설정"""
    if sys.platform == 'win32':
        # Windows: CTRL_BREAK_EVENT
        signal.signal(signal.SIGBREAK, signal_handler)
    else:
        # Unix: SIGTERM
        signal.signal(signal.SIGTERM, signal_handler)

    # 공통: SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)


def load_config():
    """환경 변수에서 설정 로드"""
    config_str = os.environ.get('PROCESS_CONFIG', '{}')
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        log("설정 파싱 실패, 기본값 사용", "WARN")
        return {}


def create_collector_config(config):
    """환경 변수 설정에서 NewsCollectorConfig 생성

    Args:
        config: 환경 변수에서 로드한 설정 딕셔너리

    Returns:
        NewsCollectorConfig: 뉴스 수집기 설정 객체
    """
    # naver_to_sheet 모듈에서 NewsCollectorConfig 가져오기
    import naver_to_sheet
    from naver_to_sheet import NewsCollectorConfig

    # 카테고리별 수집 개수
    category_counts = config.get('keywords', {})

    # category_keywords에서 실제 검색 키워드 생성
    search_keywords = {}
    keyword_map = {}
    category_keywords = config.get('category_keywords', {})

    if category_keywords and category_counts:
        for category, count in category_counts.items():
            if count <= 0:
                continue  # 0개면 해당 카테고리 스킵

            cat_data = category_keywords.get(category, {})
            core_kws = cat_data.get('core', [])
            general_kws = cat_data.get('general', [])

            # 검색용 키워드 설정 (각 키워드당 충분히 검색)
            if core_kws:
                search_count = max(5, count * 2)  # 충분히 검색
                for kw in core_kws:
                    search_keywords[kw] = search_count
                    keyword_map[kw] = category
            else:
                search_keywords[category] = count * 2
                keyword_map[category] = category

            for kw in general_kws:
                keyword_map[kw] = category

    # 기본 category_keywords 로드 (필터링용)
    default_category_keywords = naver_to_sheet.get_default_category_keywords()

    # NewsCollectorConfig 생성
    collector_config = NewsCollectorConfig(
        naver_client_id=config.get('naver_client_id', ''),
        naver_client_secret=config.get('naver_client_secret', ''),
        sheet_url=config.get('sheet_url', ''),
        category_limits=category_counts.copy() if category_counts else {"연애": 15, "경제": 15, "스포츠": 15},
        keywords=search_keywords if search_keywords else {"연애": 8, "스포츠": 20},
        keyword_category_map=keyword_map if keyword_map else {"연애": "연애", "스포츠": "스포츠"},
        category_keywords=category_keywords if category_keywords else default_category_keywords,
        display_count=config.get('display_count', 70),
        sort=config.get('sort', 'sim'),
        category_filter=None,
        skip_mismatched_category=False,
        enable_economy_category=True
    )

    return collector_config


def main():
    """메인 실행 함수"""
    global _shutdown_requested

    log("뉴스 수집 시작", "SUCCESS")

    setup_signal_handlers()
    config = load_config()

    # NewsCollectorConfig 생성 (글로벌 변수 변이 없음)
    collector_config = create_collector_config(config)

    keywords = config.get('keywords', {})
    total = sum(keywords.values())
    log(f"수집 대상: 총 {total}개 (연애 {keywords.get('연애', 0)} / 경제 {keywords.get('경제', 0)} / 스포츠 {keywords.get('스포츠', 0)})")

    if _shutdown_requested:
        log("종료 요청으로 실행 취소", "WARN")
        return

    try:
        import naver_to_sheet

        log("네이버 API 뉴스 검색 시작...")
        # main에 config 객체 전달
        naver_to_sheet.main(config=collector_config)

        log("뉴스 수집 완료", "SUCCESS")

    except KeyboardInterrupt:
        log("사용자에 의해 중단됨", "WARN")
    except Exception as e:
        log(f"오류 발생: {e}", "ERROR")
        import traceback
        traceback.print_exc()
    finally:
        log("뉴스 수집 프로세스 종료")


if __name__ == "__main__":
    main()
