# -*- coding: utf-8 -*-
"""
구글 시트의 H열(완료 표시 열)을 지속적으로 감시하여
"완료"가 포함된 행을 주기적으로 삭제하는 스크립트
"""
import sys
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random
from datetime import datetime, timezone, timedelta

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_time():
    """현재 한국 시간을 문자열로 반환"""
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==========================================
# 🔴 설정 구역 (여기를 반드시 수정하세요)
# ==========================================
# 1. 구글 시트 전체 주소
SHEET_URL = "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit"

# 2. 업로드 완료 표시 열 (H열=8번째 열, 업로드 완료 시 "완료" 표시)
COMPLETED_COLUMN = 8  # H열

# 3. 삭제 작업 실행 간격 (분 단위)
DELETE_INTERVAL = 60  # 60분마다 완료된 행 삭제 (원하는 값으로 수정 가능)

# 4. 한 번에 삭제할 최대 행 개수
MAX_DELETE_COUNT = 10  # 한 번에 최대 10개 행만 삭제 (스케줄러 사용 시 안전을 위해 제한)

# 5. API 재시도 설정
MAX_RETRIES = 5  # 최대 재시도 횟수
INITIAL_RETRY_DELAY = 60  # 초기 재시도 대기 시간 (초) - 할당량 초과 시 60초 대기
MAX_RETRY_DELAY = 300  # 최대 재시도 대기 시간 (초) - 최대 5분까지 대기
# ==========================================

def retry_with_backoff(func, *args, **kwargs):
    """API 호출 시 재시도 로직 (지수 백오프)
    
    Args:
        func: 실행할 함수
        *args, **kwargs: 함수에 전달할 인자
    
    Returns:
        함수 실행 결과
    """
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            last_exception = e
            error_code = e.response.status_code if hasattr(e, 'response') else None
            
            # 429 (할당량 초과) 오류인 경우
            if error_code == 429 or "429" in str(e) or "Quota exceeded" in str(e):
                if attempt < MAX_RETRIES - 1:
                    # 지수 백오프: 60초, 120초, 240초, 300초(최대) 순으로 대기
                    delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    # 약간의 랜덤 지터 추가 (동시 재시도 방지)
                    jitter = random.uniform(0, 10)
                    total_delay = delay + jitter
                    
                    print(f"⚠️ API 할당량 초과 (429 오류) - {attempt + 1}/{MAX_RETRIES}번째 재시도")
                    print(f"   {int(total_delay)}초 후 재시도합니다...")
                    time.sleep(total_delay)
                else:
                    print(f"❌ 최대 재시도 횟수({MAX_RETRIES}회) 초과")
                    raise
            else:
                # 429가 아닌 다른 API 오류는 즉시 재시도하지 않고 예외 발생
                raise
        except Exception as e:
            # gspread API 오류가 아닌 경우는 즉시 예외 발생
            raise
    
    # 모든 재시도 실패 시 마지막 예외 발생
    if last_exception:
        raise last_exception

def delete_completed_rows(sheet):
    """H열에 "완료"가 포함된 행을 찾아서 삭제하는 함수
    
    Args:
        sheet: gspread 시트 객체
    
    Returns:
        int: 삭제된 행의 개수
    """
    try:
        # 모든 데이터 가져오기 (매번 새로 가져와서 최신 상태 확인) - 재시도 로직 적용
        rows = retry_with_backoff(sheet.get_all_values)
        
        # 삭제할 행 번호를 저장할 리스트 (하위에서 위로 삭제하기 위해 역순 정렬)
        rows_to_delete = []
        
        # 2번째 행부터 루프 (1행은 헤더이므로 제외)
        for i, row in enumerate(rows[1:], start=2):
            # 행 데이터 길이 확인
            if len(row) < COMPLETED_COLUMN:
                continue  # H열까지 데이터가 없으면 건너뛰기
            
            # H열(완료 표시 열) 확인
            completed_status = row[COMPLETED_COLUMN - 1].strip() if row[COMPLETED_COLUMN - 1] else ""
            
            # "완료" 문자열이 포함되어 있으면 삭제 대상
            if completed_status and "완료" in completed_status:
                rows_to_delete.append(i)
        
        # 삭제할 행이 없으면 종료
        if not rows_to_delete:
            return 0
        
        # 하위에서 위로 삭제 (인덱스 오류 방지)
        rows_to_delete.sort(reverse=True)
        
        # 최대 삭제 개수 제한
        total_found = len(rows_to_delete)
        if total_found > MAX_DELETE_COUNT:
            print(f"\n[{get_kst_time()}] 삭제 대상 발견: {total_found}개 행 (최대 {MAX_DELETE_COUNT}개만 삭제)")
            rows_to_delete = rows_to_delete[:MAX_DELETE_COUNT]  # 처음 MAX_DELETE_COUNT개만 선택
            print(f"   이번에 삭제할 행 번호: {rows_to_delete} (나머지 {total_found - MAX_DELETE_COUNT}개는 다음 번에 삭제)")
        else:
            print(f"\n[{get_kst_time()}] 삭제 대상 발견: {total_found}개 행")
            print(f"   삭제할 행 번호: {rows_to_delete}")
        
        # 각 행을 삭제 (재시도 로직 적용)
        deleted_count = 0
        for row_num in rows_to_delete:
            try:
                retry_with_backoff(sheet.delete_rows, row_num)
                deleted_count += 1
                print(f"   ✅ 행 {row_num}번 삭제 완료")
            except Exception as e:
                print(f"   ❌ 행 {row_num}번 삭제 실패: {e}")
        
        return deleted_count
        
    except Exception as e:
        print(f"❌ 완료된 행 확인 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    """구글 시트를 지속적으로 감시하여 완료된 행을 주기적으로 삭제하는 메인 함수"""
    
    print("="*60)
    print("  뉴스타운 완료된 행 자동 삭제")
    print("="*60)
    print(f"\n📡 구글 시트 연결 중...")
    print(f"⏰ 삭제 작업 간격: {DELETE_INTERVAL}분")
    print(f"🛑 종료하려면 Ctrl+C를 누르세요\n")
    
    # 인증 파일 로드
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        print("✅ 인증 성공")
    except FileNotFoundError:
        print("❌ 오류: 'credentials.json' 파일을 찾을 수 없습니다.")
        print("   구글 서비스 계정 인증 파일이 필요합니다.")
        return
    except Exception as e:
        print(f"❌ 인증 오류: {e}")
        return

    # 시트 열기 (재시도 로직 적용)
    try:
        print("📡 시트 연결 시도 중...")
        doc = retry_with_backoff(client.open_by_url, SHEET_URL)
        sheet = doc.sheet1  # 첫 번째 시트 사용
        print("✅ 시트 연결 성공")
        print(f"\n👀 H열(완료 표시 열)을 감시 중...")
        print(f"   {DELETE_INTERVAL}분마다 완료된 행을 자동으로 삭제합니다.")
        print(f"   한 번에 최대 {MAX_DELETE_COUNT}개 행만 삭제합니다.\n")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    delete_count = 0
    
    # 무한 루프로 지속 감시 (오류 발생 시에도 계속 재시도)
    try:
        while True:
            try:
                delete_count += 1
                print(f"[{get_kst_time()}] {delete_count}번째 삭제 작업 시작...")
                
                deleted_rows = delete_completed_rows(sheet)
                
                if deleted_rows > 0:
                    print(f"   ✅ 총 {deleted_rows}개 행이 삭제되었습니다.")
                else:
                    print(f"   ⏸️ 삭제할 완료된 행이 없습니다.")
                
                # 다음 삭제 작업까지 대기 (분을 초로 변환)
                wait_seconds = DELETE_INTERVAL * 60
                print(f"   다음 삭제 작업까지 {DELETE_INTERVAL}분({wait_seconds}초) 대기...")
                time.sleep(wait_seconds)
                
            except gspread.exceptions.APIError as e:
                # API 오류 발생 시 재시도 로직이 이미 적용되어 있지만, 
                # 여기서도 추가 처리 (예: 시트 재연결)
                error_code = e.response.status_code if hasattr(e, 'response') else None
                if error_code == 429 or "429" in str(e) or "Quota exceeded" in str(e):
                    print(f"⚠️ API 할당량 초과 - {INITIAL_RETRY_DELAY}초 대기 후 재시도...")
                    time.sleep(INITIAL_RETRY_DELAY)
                    # 시트 재연결 시도
                    try:
                        doc = retry_with_backoff(client.open_by_url, SHEET_URL)
                        sheet = doc.sheet1
                        print("✅ 시트 재연결 성공")
                    except Exception as reconnect_error:
                        print(f"⚠️ 시트 재연결 실패: {reconnect_error}")
                        wait_seconds = DELETE_INTERVAL * 60
                        print(f"   {wait_seconds}초 후 다시 시도합니다...")
                        time.sleep(wait_seconds)
                else:
                    print(f"⚠️ API 오류 발생: {e}")
                    wait_seconds = DELETE_INTERVAL * 60
                    print(f"   {wait_seconds}초 후 다시 시도합니다...")
                    time.sleep(wait_seconds)
            except Exception as e:
                # 예상치 못한 오류 발생 시에도 계속 실행
                print(f"⚠️ 오류 발생: {e}")
                wait_seconds = DELETE_INTERVAL * 60
                print(f"   {wait_seconds}초 후 다시 시도합니다...")
                time.sleep(wait_seconds)
                
    except KeyboardInterrupt:
        print("\n\n🛑 사용자에 의해 종료되었습니다.")
        print("="*60)

if __name__ == "__main__":
    main()

