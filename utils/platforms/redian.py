# -*- coding: utf-8 -*-
"""
Redian (레디안) Platform Uploader

Redian (redian.org) automated article uploader.
Same CMS as Golftimes/Bizwnews - shares login/editor patterns.
"""
import time
import os
import json
import shutil
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .base import PlatformUploader, UploadResult, UploadStatus, PlatformConfig


# Redian URL Constants
REDIAN_URL = "https://www.redian.org"
REDIAN_LOGIN_URL = f"{REDIAN_URL}/member/login.html"
REDIAN_WRITE_URL = f"{REDIAN_URL}/news/userArticleWriteForm.html?mode=input"

# Section codes for Redian (2차 섹션 없음)
# S1N9=정치, S1N10=사회, S1N11=경제, S1N12=문화/생활, S1N8=미분류, S1N13=이슈 포커스
SECTION_1ST_CODE = "S1N10"  # 사회


class RedianUploader(PlatformUploader):
    """
    Redian (레디안) platform automated uploader.

    Same CMS as Golftimes/Bizwnews. Key differences:
    - Different base URL (redian.org), CMS at cms.redian.org
    - 1차 섹션만 사용 (2차 섹션 없음)
    - Section codes: S1N9(정치), S1N10(사회), S1N11(경제), S1N12(문화/생활), S1N8(미분류), S1N13(이슈 포커스)
    """

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.wait: Optional[WebDriverWait] = None

    def _get_chrome_driver(self, max_retries: int = 3):
        """Initialize ChromeDriver with retry logic."""
        options = webdriver.ChromeOptions()

        if self.config.headless:
            options.add_argument("--headless")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")

        chromium_path = shutil.which('chromium')
        if chromium_path:
            options.binary_location = chromium_path

        for attempt in range(max_retries):
            try:
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(30)
                driver.set_script_timeout(30)
                self.wait = WebDriverWait(driver, 10)
                return driver
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return None

        return None

    def login(self) -> bool:
        """
        Login to Redian platform.

        Uses /member/login.html (same CMS as Golftimes/Bizwnews).
        """
        try:
            if self._driver is None:
                self._driver = self._get_chrome_driver()
                if self._driver is None:
                    return False

            self._driver.get(REDIAN_LOGIN_URL)
            time.sleep(2)

            user_id = self.config.get_credential('id', '')
            user_pw = self.config.get_credential('pw', '')

            # Same CMS: text/password inputs without name attributes
            text_inputs = self.wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//input[@type='text']"))
            )
            if not text_inputs:
                raise ValueError("로그인 폼에서 텍스트 입력 필드를 찾을 수 없습니다")
            id_input = text_inputs[0]
            id_input.clear()
            id_input.send_keys(user_id)

            pw_inputs = self._driver.find_elements(By.XPATH, "//input[@type='password']")
            if not pw_inputs:
                raise ValueError("로그인 폼에서 비밀번호 입력 필드를 찾을 수 없습니다")
            pw_input = pw_inputs[0]
            pw_input.clear()
            pw_input.send_keys(user_pw)

            # Click login button
            login_clicked = False
            selectors = [
                "//button[contains(@class, 'user-bg')]",
                "//button[contains(text(), '로그인')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
            ]

            for selector in selectors:
                try:
                    login_btn = self._driver.find_element(By.XPATH, selector)
                    login_btn.click()
                    login_clicked = True
                    break
                except Exception:
                    continue

            if not login_clicked:
                try:
                    self._driver.execute_script("loginform.checkLogin();")
                    login_clicked = True
                except Exception:
                    pass

            if not login_clicked:
                print("Redian login failed: could not find login button")
                return False

            time.sleep(3)
            self._handle_alert()

            self._is_logged_in = True
            return True

        except Exception as e:
            print(f"Redian login failed: {e}")
            return False

    def _handle_alert(self) -> None:
        """Safely handle any browser alerts."""
        try:
            alert = self._driver.switch_to.alert
            alert.accept()
        except Exception:
            pass

    def _input_content_via_ckeditor(self, content: str) -> bool:
        """Input content using CKEditor."""
        try:
            # 본문 HTML 생성
            lines = content.split('\n')
            html_paragraphs = [f"<p>{line.strip()}</p>" for line in lines if line.strip()]
            new_html = ''.join(html_paragraphs) if html_paragraphs else f"<p>{content}</p>"

            # CKEditor에 설정
            js_script = f"CKEDITOR.instances['FCKeditor1'].setData({json.dumps(new_html)});"
            self._driver.execute_script(js_script)

            return True
        except Exception:
            return False

    def _click_submit_button(self) -> bool:
        """Click the submit button to publish article."""
        try:
            submit_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.success.expanded.large"))
            )
            submit_btn.click()
            return True
        except Exception:
            pass

        try:
            submit_btn = self._driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_btn.click()
            return True
        except Exception:
            pass

        try:
            submit_btn = self._driver.find_element(By.XPATH, "//button[contains(text(), '저장')]")
            submit_btn.click()
            return True
        except Exception:
            pass

        try:
            self._driver.execute_script("document.newsWriteForm.submit();")
            return True
        except Exception:
            pass

        return False

    def upload(self, title: str, content: str, category: Optional[str] = None, submit: bool = False) -> UploadResult:
        """
        Upload article to Redian.

        Args:
            title: Article title
            content: Article body content
            category: Optional category (not used)
            submit: If False, only fill form without submitting (default: False)
        """
        try:
            if self._driver is None:
                self._driver = self._get_chrome_driver()
                if self._driver is None:
                    return UploadResult(
                        success=False, platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="ChromeDriver initialization failed"
                    )

            if not self._is_logged_in:
                if not self.login():
                    return UploadResult(
                        success=False, platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="Login failed"
                    )

            self._driver.get(REDIAN_WRITE_URL)
            time.sleep(2)

            # Select 1st section (레디안은 2차 섹션 없음)
            section1_select = Select(self._driver.find_element(By.NAME, "sectionCode"))
            section1_select.select_by_value(SECTION_1ST_CODE)
            time.sleep(1)

            # Enter title
            title_input = self._driver.find_element(By.NAME, "title")
            title_input.clear()
            title_input.send_keys(title)

            # Enter content via CKEditor
            if not self._input_content_via_ckeditor(content):
                return UploadResult(
                    success=False, platform=self.platform_name,
                    status=UploadStatus.FAILED,
                    error_message="Failed to input content via CKEditor"
                )

            if submit:
                time.sleep(2)
                if not self._click_submit_button():
                    return UploadResult(
                        success=False, platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="Failed to click submit button"
                    )
                time.sleep(5)
                self._handle_alert()
                print("레디안 기사 제출 완료")
            else:
                print("레디안 입력 완료 (제출하지 않음)")

            return UploadResult(
                success=True, platform=self.platform_name,
                status=UploadStatus.SUCCESS,
                metadata={"title_length": len(title), "submitted": submit}
            )

        except Exception as e:
            return UploadResult(
                success=False, platform=self.platform_name,
                status=UploadStatus.FAILED,
                error_message=str(e)
            )

    def logout(self) -> bool:
        self._is_logged_in = False
        return True

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'RedianUploader':
        """Create RedianUploader from config dictionary."""
        if 'redian' in config_dict:
            rd_config = config_dict['redian']
        else:
            rd_config = config_dict

        rd_id = (
            rd_config.get('redian_id') or
            rd_config.get('site_id') or
            os.environ.get('REDIAN_ID', '')
        )
        rd_pw = (
            rd_config.get('redian_pw') or
            rd_config.get('site_pw') or
            os.environ.get('REDIAN_PW', '')
        )

        config = PlatformConfig(
            platform_name="redian",
            login_url=REDIAN_LOGIN_URL,
            write_url=REDIAN_WRITE_URL,
            credentials={"id": rd_id, "pw": rd_pw},
            enabled=rd_config.get('enabled', True),
            timeout=rd_config.get('timeout', 120),
            headless=rd_config.get('headless', True),
            extra_params={
                'headless': rd_config.get('headless', True),
            }
        )

        return cls(config)


def upload_to_redian(title: str, content: str,
                     config: Optional[Dict[str, Any]] = None,
                     submit: bool = False) -> UploadResult:
    """Convenience function for single upload to Redian."""
    if config is None:
        config = {}

    uploader = RedianUploader.from_config({'redian': config})

    try:
        result = uploader.upload(title, content, submit=submit)
        return result
    finally:
        uploader.close()
