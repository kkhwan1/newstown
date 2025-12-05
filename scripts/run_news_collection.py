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

# 종료 플래그
_shutdown_requested = False

def signal_handler(signum, frame):
    """신호 핸들러 - graceful shutdown"""
    global _shutdown_requested
    print(f"\n[WARN] 종료 신호 수신 (signal={signum}), 정리 중...")
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
        print("[WARN] 설정 파싱 실패, 기본값 사용")
        return {}

def apply_config(config):
    """naver_to_sheet 모듈의 전역 변수 오버라이드"""
    import naver_to_sheet

    # 카테고리별 수집 개수
    category_counts = config.get('keywords', {})
    
    # category_keywords에서 실제 검색 키워드 생성
    if 'category_keywords' in config and category_counts:
        search_keywords = {}
        keyword_map = {}
        
        for category, count in category_counts.items():
            cat_data = config['category_keywords'].get(category, {})
            core_kws = cat_data.get('core', [])
            general_kws = cat_data.get('general', [])
            
            # Core 키워드를 실제 검색에 사용
            if core_kws:
                # 각 core 키워드에 수집 개수 분배
                per_keyword_count = max(1, count // len(core_kws))
                for kw in core_kws:
                    search_keywords[kw] = per_keyword_count
                    keyword_map[kw] = category
            else:
                # core 키워드가 없으면 카테고리명 자체를 사용
                search_keywords[category] = count
                keyword_map[category] = category
            
            # General 키워드도 카테고리 매핑에 추가 (분류용)
            for kw in general_kws:
                keyword_map[kw] = category
        
        if search_keywords:
            naver_to_sheet.KEYWORDS = search_keywords
            print(f"[CONFIG] 검색 키워드: {len(search_keywords)}개")
            for kw, cnt in search_keywords.items():
                print(f"   - {kw}: {cnt}개")
        
        if keyword_map:
            naver_to_sheet.KEYWORD_CATEGORY_MAP = keyword_map
            print(f"[CONFIG] 카테고리 매핑: {len(keyword_map)}개")
    
    elif 'keywords' in config:
        # category_keywords가 없는 경우 기존 방식 사용
        naver_to_sheet.KEYWORDS = config['keywords']
        print(f"[CONFIG] 키워드 설정 (기본): {config['keywords']}")

    # 출력 개수 설정
    if 'display_count' in config:
        naver_to_sheet.DISPLAY_COUNT = config['display_count']
        print(f"[CONFIG] 출력 개수: {config['display_count']}")

    # 구글 시트 URL
    if 'sheet_url' in config:
        naver_to_sheet.SHEET_URL = config['sheet_url']
        print(f"[CONFIG] 시트 URL: {config['sheet_url'][:50]}...")

    # 네이버 API 설정
    if 'naver_client_id' in config:
        naver_to_sheet.NAVER_CLIENT_ID = config['naver_client_id']
    if 'naver_client_secret' in config:
        naver_to_sheet.NAVER_CLIENT_SECRET = config['naver_client_secret']

def main():
    """메인 실행 함수"""
    global _shutdown_requested

    print("="*60)
    print("  뉴스 수집 러너 시작")
    print("="*60)

    # 신호 핸들러 설정
    setup_signal_handlers()

    # 설정 로드 및 적용
    config = load_config()
    print(f"[INFO] 설정 로드됨: {json.dumps(config, ensure_ascii=False, indent=2)}")

    # 설정 적용
    apply_config(config)

    # 종료 확인
    if _shutdown_requested:
        print("[STOP] 종료 요청으로 실행 취소")
        return

    try:
        # naver_to_sheet의 main 함수 실행
        import naver_to_sheet
        naver_to_sheet.main()

        print("\n[OK] 뉴스 수집 완료")

    except KeyboardInterrupt:
        print("\n[STOP] 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("="*60)
        print("  뉴스 수집 러너 종료")
        print("="*60)

if __name__ == "__main__":
    main()
