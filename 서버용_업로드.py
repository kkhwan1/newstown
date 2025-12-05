# -*- coding: utf-8 -*-
import sys
import io
import time
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==========================================
# 🔴 설정 구역 (여기를 반드시 수정하세요)
# ==========================================
# 뉴스타운 아이디 / 비밀번호
SITE_ID = "kim123"
SITE_PW = "love1105()"

# Flask 서버 포트
FLASK_PORT = 7777
# ==========================================

# Flask 앱 생성
app = Flask(__name__)

def get_chrome_driver():
    """ChromeDriver 초기화 함수 (공통)"""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # 창을 안 보고 싶으면 이 줄의 주석(#)을 지우세요
    options.add_argument("--start-maximized") # 창 최대화
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ ChromeDriver 자동 설치 완료")
    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ ChromeDriverManager 오류: {error_msg}")
        if "WinError 193" in error_msg or "올바른 Win32 응용 프로그램이 아닙니다" in error_msg:
            print("   시스템 PATH의 ChromeDriver 사용 시도 중...")
            try:
                driver = webdriver.Chrome(options=options)
                print("✅ 시스템 PATH의 ChromeDriver 사용 성공")
            except Exception as e2:
                print(f"❌ ChromeDriver 초기화 실패: {e2}")
                print("   Chrome 브라우저를 최신 버전으로 업데이트하거나 ChromeDriver를 수동으로 설치해주세요.")
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

def upload_to_newstown(title, content):
    """뉴스타운에 기사를 자동으로 업로드하는 함수 (셀레니움)"""
    
    driver = get_chrome_driver()
    if driver is None:
        return False
    
    wait = WebDriverWait(driver, 15)

    try:
        print(f"\n🚀 [시작] '{title}' 업로드를 시작합니다.")

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
            
            # 2차 섹션 드롭다운 찾기 및 선택
            sub_section_element = wait.until(EC.presence_of_element_located((By.NAME, "subSectionCode")))
            sub_section_select = Select(sub_section_element)
            sub_section_select.select_by_visible_text("연예")
            print("✅ 2차 섹션 선택: 연예")
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
        print("✅ 업로드 작업 완료!")
        return True

    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        return False
    finally:
        # 브라우저 닫기
        driver.quit()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Make.com에서 웹훅으로 데이터를 받아 업로드하는 엔드포인트"""
    try:
        # JSON 데이터 받기
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'JSON 데이터가 없습니다.'
            }), 400
        
        # articles 배열 확인
        articles = data.get('articles', [])
        
        if not articles:
            return jsonify({
                'success': False,
                'error': 'articles 배열이 없거나 비어있습니다.'
            }), 400
        
        if not isinstance(articles, list):
            return jsonify({
                'success': False,
                'error': 'articles는 배열이어야 합니다.'
            }), 400
        
        print(f"\n📥 웹훅 수신: {len(articles)}개의 기사 업로드 요청")
        
        # 결과 저장
        results = []
        success_count = 0
        fail_count = 0
        
        # 각 기사를 순차적으로 업로드
        for idx, article in enumerate(articles, 1):
            title = article.get('title', '')
            content = article.get('content', '')
            
            if not title or not content:
                results.append({
                    'index': idx,
                    'title': title[:30] if title else '(제목 없음)',
                    'success': False,
                    'error': '제목 또는 본문이 없습니다.'
                })
                fail_count += 1
                continue
            
            print(f"\n[{idx}/{len(articles)}] '{title[:30]}...' 업로드 시작...")
            
            # 업로드 실행
            success = upload_to_newstown(title, content)
            
            if success:
                results.append({
                    'index': idx,
                    'title': title[:30],
                    'success': True,
                    'message': '업로드 완료'
                })
                success_count += 1
                print(f"✅ [{idx}/{len(articles)}] 업로드 성공")
            else:
                results.append({
                    'index': idx,
                    'title': title[:30],
                    'success': False,
                    'error': '업로드 실패 (로그 확인)'
                })
                fail_count += 1
                print(f"❌ [{idx}/{len(articles)}] 업로드 실패")
        
        # 전체 결과 반환
        return jsonify({
            'success': True,
            'total': len(articles),
            'success_count': success_count,
            'fail_count': fail_count,
            'results': results
        }), 200
        
    except Exception as e:
        print(f"❌ 웹훅 처리 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """서버 상태 확인 엔드포인트"""
    return jsonify({
        'status': 'ok',
        'message': 'Flask 서버가 정상적으로 실행 중입니다.'
    }), 200

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Flask 웹훅 서버 시작")
    print("="*60)
    print(f"\n포트: {FLASK_PORT}")
    print(f"웹훅 URL: http://localhost:{FLASK_PORT}/webhook")
    print(f"상태 확인: http://localhost:{FLASK_PORT}/health")
    print(f"\n서버를 시작합니다...")
    print("="*60 + "\n")
    
    # Flask 서버 실행 (모든 인터페이스에서 접근 가능하도록 0.0.0.0 사용)
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False)