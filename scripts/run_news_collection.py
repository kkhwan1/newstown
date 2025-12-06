# -*- coding: utf-8 -*-
"""
뉴스 수집 래퍼 스크립트
대시보드에서 서브프로세스로 실행되며, 환경 변수로 설정을 받아 실행
"""
import sys
import os
import io
import json
import signal

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 부모 디렉토리를 path에 추가 (naver_to_sheet.py import를 위해)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.logger import add_log

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")
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

def apply_config(config):
    """naver_to_sheet 모듈의 전역 변수 오버라이드"""
    import naver_to_sheet

    # 카테고리별 수집 개수 (이것이 실제 저장할 개수!)
    category_counts = config.get('keywords', {})
    
    # 핵심: 카테고리별 목표 개수를 별도 변수로 전달
    naver_to_sheet.CATEGORY_LIMITS = category_counts.copy()
    log(f"카테고리별 목표 개수: 연애={category_counts.get('연애', 0)}, 경제={category_counts.get('경제', 0)}, 스포츠={category_counts.get('스포츠', 0)}")
    
    # category_keywords에서 실제 검색 키워드 생성
    if 'category_keywords' in config and category_counts:
        search_keywords = {}
        keyword_map = {}
        
        for category, count in category_counts.items():
            if count <= 0:
                continue  # 0개면 해당 카테고리 스킵
                
            cat_data = config['category_keywords'].get(category, {})
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
        
        if search_keywords:
            naver_to_sheet.KEYWORDS = search_keywords
            log(f"검색 키워드: {len(search_keywords)}개 설정됨")
        
        if keyword_map:
            naver_to_sheet.KEYWORD_CATEGORY_MAP = keyword_map
            log(f"카테고리 매핑: {len(keyword_map)}개 설정됨")
    
    elif 'keywords' in config:
        naver_to_sheet.KEYWORDS = config['keywords']
        log(f"키워드 설정: {config['keywords']}")

    if 'display_count' in config:
        naver_to_sheet.DISPLAY_COUNT = config['display_count']

    if 'sheet_url' in config:
        naver_to_sheet.SHEET_URL = config['sheet_url']
        log(f"시트 URL 설정됨")

    if 'naver_client_id' in config:
        naver_to_sheet.NAVER_CLIENT_ID = config['naver_client_id']
    if 'naver_client_secret' in config:
        naver_to_sheet.NAVER_CLIENT_SECRET = config['naver_client_secret']
    
    if 'sort' in config:
        naver_to_sheet.SORT_OPTION = config['sort']
        sort_name = "인기순" if config['sort'] == 'sim' else "최신순"
        log(f"정렬 방식: {sort_name}")

def main():
    """메인 실행 함수"""
    global _shutdown_requested

    log("뉴스 수집 시작", "SUCCESS")

    setup_signal_handlers()
    config = load_config()
    
    keywords = config.get('keywords', {})
    total = sum(keywords.values())
    log(f"수집 대상: 총 {total}개 (연애 {keywords.get('연애', 0)} / 경제 {keywords.get('경제', 0)} / 스포츠 {keywords.get('스포츠', 0)})")

    apply_config(config)

    if _shutdown_requested:
        log("종료 요청으로 실행 취소", "WARN")
        return

    try:
        import naver_to_sheet
        
        log("네이버 API 뉴스 검색 시작...")
        naver_to_sheet.main()

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
