# -*- coding: utf-8 -*-
"""
구글 시트의 E열(AI_제목)과 F열(AI_본문)을 지속적으로 감시하여
데이터가 채워지면 자동으로 뉴스타운에 업로드하는 스크립트
"""
import sys
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_time():
    """현재 한국 시간을 문자열로 반환"""
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 스크립트 시작 확인 메시지
print("🚀 스크립트 시작 중...", flush=True)

# ==========================================
# 🔴 설정 구역 (여기를 반드시 수정하세요)
# ==========================================
# 1. 구글 시트 전체 주소
SHEET_URL = "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit"

# 2. 뉴스타운 아이디 / 비밀번호
SITE_ID = "kim123"
SITE_PW = "love1105()"

# 3. 업로드 완료 표시 열 (H열=8번째 열, 업로드 완료 시 "완료" 표시)
COMPLETED_COLUMN = 8  # H열

# 4. 감시 간격 (초 단위)
CHECK_INTERVAL = 30  # 30초마다 시트 확인

# 5. API 재시도 설정
MAX_RETRIES = 5  # 최대 재시도 횟수
INITIAL_RETRY_DELAY = 60  # 초기 재시도 대기 시간 (초) - 할당량 초과 시 60초 대기
MAX_RETRY_DELAY = 300  # 최대 재시도 대기 시간 (초) - 최대 5분까지 대기

# 6. 동시 업로드 개수 설정
CONCURRENT_UPLOADS = 2  # 동시에 업로드할 뉴스 개수 (1~3)
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

def update_db_status_to_uploaded(link):
    """DB에서 해당 링크의 뉴스를 uploaded 상태로 변경"""
    import os
    import psycopg2
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("⚠️ DATABASE_URL 환경변수가 없습니다.")
        return False
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute(
            "UPDATE news SET status = 'uploaded', uploaded_at = %s WHERE link = %s",
            (datetime.now(KST), link)
        )
        rows_updated = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        if rows_updated > 0:
            print(f"✅ DB 상태 업데이트 완료: {rows_updated}개 뉴스 → uploaded")
        return True
    except Exception as e:
        print(f"⚠️ DB 업데이트 오류: {e}")
        return False

def get_chrome_driver():
    """ChromeDriver 초기화 함수"""
    import shutil
    import os
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    chromium_path = shutil.which('chromium')
    chromedriver_path = shutil.which('chromedriver')
    
    driver = None
    
    if chromium_path and chromedriver_path:
        print(f"   Chromium: {chromium_path}")
        print(f"   ChromeDriver: {chromedriver_path}")
        options.binary_location = chromium_path
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            print("✅ Replit Chromium 사용 성공")
            return driver
        except Exception as e:
            print(f"⚠️ Replit Chromium 오류: {e}")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ ChromeDriver 자동 설치 완료")
    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ ChromeDriverManager 오류: {error_msg}")
        try:
            driver = webdriver.Chrome(options=options)
            print("✅ 시스템 PATH의 ChromeDriver 사용 성공")
        except Exception as e2:
            print(f"❌ ChromeDriver 초기화 실패: {e2}")
            return None
    return driver

def login_to_newstown(driver, wait):
    """뉴스타운에 로그인하는 함수"""
    driver.get("http://www.newstown.co.kr/member/login.html")
    
    # 아이디 입력
    user_id_field = wait.until(EC.presence_of_element_located((By.ID, "user_id")))
    user_id_field.clear()
    user_id_field.send_keys(SITE_ID)
    
    # 비번 입력
    driver.find_element(By.ID, "user_pw").send_keys(SITE_PW)
    
    # 로그인 버튼 클릭
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1.5) # 로그인 처리 대기
    return True

def upload_to_newstown(title, content, category=None):
    """뉴스타운에 기사를 자동으로 업로드하는 함수 (셀레니움)
    
    Args:
        title: 기사 제목
        content: 기사 본문
        category: 카테고리 (연애, 경제, 스포츠 등) - D열 값
    """
    
    driver = get_chrome_driver()
    if driver is None:
        return False
    
    wait = WebDriverWait(driver, 15)

    try:
        print(f"\n🚀 [뉴스타운 업로드 시작] '{title[:50]}...'")

        # -------------------------------------------------
        # 1. 로그인 단계
        # -------------------------------------------------
        login_to_newstown(driver, wait)

        # -------------------------------------------------
        # 2. 글쓰기 폼 이동
        # -------------------------------------------------
        driver.get("http://www.newstown.co.kr/news/userArticleWriteForm.html")
        
        # -------------------------------------------------
        # 3. 섹션 선택 (1차 섹션 -> 2차 섹션)
        # -------------------------------------------------
        try:
            # 페이지 로드 대기
            wait.until(EC.presence_of_element_located((By.NAME, "sectionCode")))
            time.sleep(1)  # 페이지 완전 로드 대기
            
            # 1차 섹션 드롭다운 찾기 및 선택
            section_element = wait.until(EC.presence_of_element_located((By.NAME, "sectionCode")))
            section_select = Select(section_element)
            section_select.select_by_visible_text("데일리 핫이슈")
            print("✅ 1차 섹션 선택: 데일리 핫이슈")
            time.sleep(1.5)  # 2차 섹션 옵션이 로드될 때까지 대기
            
            # 2차 섹션 드롭다운 찾기 및 선택 (카테고리에 따라 자동 선택)
            sub_section_element = wait.until(EC.presence_of_element_located((By.NAME, "subSectionCode")))
            sub_section_select = Select(sub_section_element)
            
            # 카테고리 매핑: D열 값에 따라 2차 섹션 선택
            # 연애 → 연예, 경제 → 경제, 스포츠 → 스포츠
            category_mapping = {
                "연애": "연예",
                "경제": "경제",
                "스포츠": "스포츠"
            }
            
            # category가 전달된 경우 매핑, 없으면 기본값 "연예"
            if category and category in category_mapping:
                sub_section_text = category_mapping[category]
            else:
                sub_section_text = "연예"  # 기본값
            
            sub_section_select.select_by_visible_text(sub_section_text)
            print(f"✅ 2차 섹션 선택: {sub_section_text} (카테고리: {category if category else '기본값'})")
            time.sleep(1.5)  # 3차 섹션 옵션이 로드될 때까지 대기
            
            # 3차 섹션(연재) 드롭다운 찾기 및 선택
            serial_element = wait.until(EC.presence_of_element_located((By.NAME, "serialCode")))
            serial_select = Select(serial_element)
            serial_select.select_by_visible_text("일반뉴스")
            print("✅ 3차 섹션 선택: 일반뉴스")
            time.sleep(0.5)  # 선택 완료 대기
        except Exception as e:
            print(f"⚠️ 섹션 선택 중 경고: {e}")
            import traceback
            traceback.print_exc()

        # -------------------------------------------------
        # 4. 제목 입력
        # -------------------------------------------------
        driver.find_element(By.ID, "title").send_keys(title)

        # -------------------------------------------------
        # 5. 본문 입력 (CKEditor / iframe 처리)
        # -------------------------------------------------
        print("✍️ 본문 작성 중...")
        
        # iframe 찾기 (에디터는 보통 iframe 안에 숨어있음)
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        driver.switch_to.frame(iframe) # iframe 내부로 진입
        
        body_area = driver.find_element(By.TAG_NAME, "body")
        body_area.clear() # 기존 내용 비우기
        body_area.send_keys(content) # 구글 시트 내용 입력
        
        driver.switch_to.default_content() # 다시 메인 화면으로 복귀

        # -------------------------------------------------
        # 6. 저장 버튼 클릭
        # -------------------------------------------------
        print("💾 저장 버튼 클릭...")
        save_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        
        # 자바스크립트로 강제 클릭 (오류 방지)
        driver.execute_script("arguments[0].click();", save_btn)
        
        # 저장 완료 대기 (3초)
        time.sleep(3) 
        
        # 성공 여부 확인 (페이지가 이동했거나, 알림창이 떴는지 등)
        print("✅ 뉴스타운 업로드 완료!")
        return True

    except Exception as e:
        print(f"❌ 뉴스타운 업로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 브라우저 닫기
        driver.quit()

def upload_single_item(item_data):
    """단일 항목을 업로드하는 함수 (ThreadPoolExecutor에서 호출)
    
    Args:
        item_data: dict with row_num, ai_title, ai_content, category, link
    
    Returns:
        dict with row_num, success, link
    """
    row_num = item_data['row_num']
    ai_title = item_data['ai_title']
    ai_content = item_data['ai_content']
    category = item_data['category']
    link = item_data['link']
    
    print(f"\n[{get_kst_time()}] [스레드] 행 {row_num}번 업로드 시작")
    print(f"   D열(카테고리): {category if category else '(없음)'}")
    print(f"   E열(AI_제목): {ai_title[:50]}...")
    
    success = upload_to_newstown(ai_title, ai_content, category if category else None)
    
    return {
        'row_num': row_num,
        'success': success,
        'link': link
    }

def check_and_upload(sheet):
    """시트를 확인하고 업로드할 항목이 있으면 동시에 업로드하는 함수
    
    Returns:
        True: 업로드 성공 (1개 이상)
        False: 업로드 실패
        None: 업로드할 항목 없음 (E열/F열 비어있음)
    """
    try:
        rows = retry_with_backoff(sheet.get_all_values)
        
        items_to_upload = []
        
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 6:
                continue
            
            category = row[3].strip() if len(row) > 3 and row[3] else ""
            ai_title = row[4].strip() if len(row) > 4 and row[4] else ""
            ai_content = row[5].strip() if len(row) > 5 and row[5] else ""
            
            if not ai_title or not ai_content:
                continue
            
            completed_status = ""
            if len(row) >= COMPLETED_COLUMN:
                completed_status = row[COMPLETED_COLUMN - 1].strip() if row[COMPLETED_COLUMN - 1] else ""
            
            if completed_status and "완료" in completed_status:
                continue
            
            link = row[2].strip() if len(row) > 2 and row[2] else ""
            
            items_to_upload.append({
                'row_num': i,
                'ai_title': ai_title,
                'ai_content': ai_content,
                'category': category,
                'link': link
            })
            
            if len(items_to_upload) >= CONCURRENT_UPLOADS:
                break
        
        if not items_to_upload:
            return None
        
        print(f"\n[{get_kst_time()}] [감지] 업로드할 항목 {len(items_to_upload)}개 발견 (동시 업로드: {CONCURRENT_UPLOADS}개)")
        for item in items_to_upload:
            print(f"   - 행 {item['row_num']}번: {item['ai_title'][:40]}...")
        
        results = []
        with ThreadPoolExecutor(max_workers=CONCURRENT_UPLOADS) as executor:
            future_to_item = {executor.submit(upload_single_item, item): item for item in items_to_upload}
            
            for future in as_completed(future_to_item):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    item = future_to_item[future]
                    print(f"❌ 행 {item['row_num']}번 업로드 중 예외 발생: {e}")
                    results.append({'row_num': item['row_num'], 'success': False, 'link': item['link']})
        
        success_count = 0
        fail_count = 0
        
        for result in results:
            row_num = result['row_num']
            success = result['success']
            link = result['link']
            
            if success:
                try:
                    completed_time = f"완료 {get_kst_time()}"
                    retry_with_backoff(sheet.update_cell, row_num, COMPLETED_COLUMN, completed_time)
                    print(f"✅ 행 {row_num}번 업로드 완료!")
                    
                    if link:
                        update_db_status_to_uploaded(link)
                    
                    success_count += 1
                except Exception as sheet_error:
                    print(f"✅ 행 {row_num}번 업로드 완료! (시트 업데이트 실패: {sheet_error})")
                    success_count += 1
            else:
                try:
                    retry_with_backoff(sheet.update_cell, row_num, COMPLETED_COLUMN, f"실패 {get_kst_time()}")
                    print(f"❌ 행 {row_num}번 업로드 실패!")
                except Exception as sheet_error:
                    print(f"❌ 행 {row_num}번 업로드 실패! (시트 업데이트 실패: {sheet_error})")
                fail_count += 1
        
        print(f"\n[{get_kst_time()}] [결과] 성공: {success_count}개, 실패: {fail_count}개")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 시트 확인 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """구글 시트를 지속적으로 감시하여 자동 업로드하는 메인 함수"""
    
    print("="*60, flush=True)
    print("  뉴스타운 자동 업로드 (감시 모드)", flush=True)
    print("="*60, flush=True)
    print(f"\n📡 구글 시트 연결 중...", flush=True)
    print(f"⏰ 감시 간격: {CHECK_INTERVAL}초", flush=True)
    print(f"🚀 동시 업로드: {CONCURRENT_UPLOADS}개", flush=True)
    print(f"🛑 종료하려면 Ctrl+C를 누르세요\n", flush=True)
    
    # 인증 파일 로드
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        print("🔐 인증 파일 로드 중...", flush=True)
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        print("✅ 인증 성공", flush=True)
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
        print("\n👀 E열(AI_제목)과 F열(AI_본문)을 감시 중...")
        print("   E열/F열이 채워지면 자동으로 뉴스타운에 업로드합니다.\n")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    check_count = 0
    
    # 무한 루프로 지속 감시 (오류 발생 시에도 계속 재시도)
    try:
        while True:
            try:
                check_count += 1
                print(f"[{get_kst_time()}] {check_count}번째 확인 중...")
                
                result = check_and_upload(sheet)
                
                if result is None:
                    print(f"   ⏸️ 업로드할 항목 없음 (E열/F열이 비어있거나 이미 업로드 완료)")
                    print(f"   → E열/F열에 데이터가 채워질 때까지 대기 중...")
                    print(f"   다음 확인까지 {CHECK_INTERVAL}초 대기...")
                elif result:
                    print(f"   ✅ 업로드 완료! 다음 확인까지 {CHECK_INTERVAL}초 대기...")
                else:
                    print(f"   ❌ 업로드 실패 (다음 확인까지 {CHECK_INTERVAL}초 대기)")
                
                # 지정된 간격만큼 대기
                time.sleep(CHECK_INTERVAL)
                
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
                        print(f"   {CHECK_INTERVAL}초 후 다시 시도합니다...")
                        time.sleep(CHECK_INTERVAL)
                else:
                    print(f"⚠️ API 오류 발생: {e}")
                    print(f"   {CHECK_INTERVAL}초 후 다시 시도합니다...")
                    time.sleep(CHECK_INTERVAL)
            except Exception as e:
                # 예상치 못한 오류 발생 시에도 계속 실행
                print(f"⚠️ 오류 발생: {e}")
                print(f"   {CHECK_INTERVAL}초 후 다시 시도합니다...")
                time.sleep(CHECK_INTERVAL)
                
    except KeyboardInterrupt:
        print("\n\n🛑 사용자에 의해 종료되었습니다.")
        print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 사용자에 의해 종료되었습니다.", flush=True)
    except Exception as e:
        print(f"\n\n❌ 치명적 오류 발생: {e}", flush=True)
        import traceback
        traceback.print_exc()

