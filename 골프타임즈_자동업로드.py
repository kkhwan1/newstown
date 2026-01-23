# coding: utf-8
"""
골프타임즈(thegolftimes.co.kr) 자동 업로드 모듈

The Golf Times 자동화를 위한 Selenium 기반 업로더
"""

import time
import traceback
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

GOLFTIMES_URL = "https://www.thegolftimes.co.kr"
GOLFTIMES_LOGIN_URL = f"{GOLFTIMES_URL}/member/login.html"
GOLFTIMES_WRITE_URL = f"{GOLFTIMES_URL}/news/userArticleWriteForm.html?mode=input"

_process_config = {}
if os.environ.get('PROCESS_CONFIG'):
    try:
        _process_config = json.loads(os.environ.get('PROCESS_CONFIG', '{}'))
    except:
        pass

GOLFTIMES_ID = _process_config.get('golftimes_id', "thegolftimes")
GOLFTIMES_PW = _process_config.get('golftimes_pw', "Golf1220")

SECTION_1ST = "S1N5"
SECTION_2ND = "S2N28"


class GolfTimesUploader:
    """골프타임즈 자동 업로드 클래스"""

    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.wait = None

    def get_driver(self):
        """ChromeDriver 초기화 및 실행"""
        options = webdriver.ChromeOptions()

        if self.headless:
            options.add_argument("--headless")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        try:
            try:
                import shutil
                chromium_path = shutil.which('chromium')
                if chromium_path:
                    options.binary_location = chromium_path
            except:
                pass

            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 10)
            print("✅ [골프타임즈] ChromeDriver 실행 성공")
            return self.driver
        except Exception as e:
            print(f"❌ [골프타임즈] ChromeDriver 실행 실패: {e}")
            traceback.print_exc()
            return None

    def login(self):
        """골프타임즈 로그인"""
        try:
            print("[골프타임즈] 로그인 페이지 이동...")
            self.driver.get(GOLFTIMES_LOGIN_URL)
            time.sleep(2)

            id_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "user_id")))
            id_input.clear()
            id_input.send_keys(GOLFTIMES_ID)
            print("[골프타임즈] 아이디 입력 완료")

            pw_input = self.driver.find_element(By.NAME, "user_pw")
            pw_input.clear()
            pw_input.send_keys(GOLFTIMES_PW)
            print("[골프타임즈] 비밀번호 입력 완료")

            login_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.login_submit")))
            login_btn.click()
            print("[골프타임즈] 로그인 버튼 클릭")

            time.sleep(3)

            try:
                alert = self.driver.switch_to.alert
                alert.accept()
                print("[골프타임즈] Alert 확인 및 처리")
            except:
                pass

            print("[골프타임즈] 로그인 성공")
            return True

        except Exception as e:
            print(f"[골프타임즈] 로그인 실패: {e}")
            traceback.print_exc()
            return False

    def write_article(self, title, content):
        """기사 작성"""
        try:
            print("[골프타임즈] 기사 작성 페이지 이동...")
            self.driver.get(GOLFTIMES_WRITE_URL)
            time.sleep(1)

            print("[골프타임즈] 1차 섹션 선택 (문화)...")
            section1_select = Select(
                self.driver.find_element(By.NAME, "sectionCode"))
            section1_select.select_by_value(SECTION_1ST)

            time.sleep(1)

            print("[골프타임즈] 2차 섹션 선택 (핫이슈)...")
            section2_select = Select(
                self.driver.find_element(By.NAME, "subSectionCode"))
            section2_select.select_by_value(SECTION_2ND)

            print(f"[골프타임즈] 제목 입력: {title[:30]}...")
            title_input = self.driver.find_element(By.NAME, "title")
            title_input.clear()
            title_input.send_keys(title)

            print("[골프타임즈] 본문 입력 (CKEditor)...")
            html_content = content.replace("`",
                                           "\\`").replace("$", "\\$").replace(
                                               "\n", "<br>")
            js_script = f"CKEDITOR.instances['FCKeditor1'].setData('<p>{html_content}</p>');"
            self.driver.execute_script(js_script)

            print("[골프타임즈] 등록 버튼 클릭...")
            try:
                submit_btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='newsWriteFormSubmit']")))
                submit_btn.click()
            except:
                try:
                    submit_btn = self.driver.find_element(By.XPATH, "//a[contains(text(), '등록')]")
                    submit_btn.click()
                except:
                    self.driver.execute_script("newsWriteFormSubmit();")
            
            print("[골프타임즈] 등록 버튼 클릭 완료")

            time.sleep(5)

            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                print(f"[골프타임즈] Alert 메시지: {alert_text}")
                alert.accept()
                print("[골프타임즈] 등록 후 Alert 확인 및 처리")
            except:
                pass

            print("[골프타임즈] 기사 작성 완료")
            return True

        except Exception as e:
            print(f"[골프타임즈] 기사 작성 실패: {e}")
            traceback.print_exc()
            return False

    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            print("[골프타임즈] 브라우저 종료")


def upload_to_golftimes(title, content, headless=True):
    """골프타임즈 업로드 진입점 함수"""
    uploader = GolfTimesUploader(headless=headless)

    try:
        if not uploader.get_driver():
            return False

        if not uploader.login():
            return False

        if not uploader.write_article(title, content):
            return False

        print("✅ [골프타임즈] 업로드 성공")
        return True

    except Exception as e:
        print(f"❌ [골프타임즈] 업로드 중 오류: {e}")
        traceback.print_exc()
        return False

    finally:
        uploader.close()


if __name__ == "__main__":
    test_title = "[테스트] 자동 업로드 테스트 기사입니다"
    test_content = """
    이것은 골프타임즈 자동 업로드 테스트 기사입니다.
    Selenium을 통한 자동화가 정상적으로 작동하는지 확인합니다.
    """

    print("=" * 50)
    print("골프타임즈 자동 업로드 테스트 시작")
    print("=" * 50)

    result = upload_to_golftimes(test_title, test_content, headless=False)

    print("=" * 50)
    print(f"테스트 결과: {'성공 ✅' if result else '실패 ❌'}")
    print("=" * 50)
