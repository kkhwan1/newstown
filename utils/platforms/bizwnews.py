# -*- coding: utf-8 -*-
"""
Bizwnews (비즈월드) Platform Uploader

Bizwnews (bizwnews.com) automated article uploader.
Same CMS as Golftimes - shares login/editor patterns.
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


# Bizwnews URL Constants
BIZWNEWS_URL = "https://www.bizwnews.com"
BIZWNEWS_LOGIN_URL = f"{BIZWNEWS_URL}/member/login.html"
BIZWNEWS_WRITE_URL = f"{BIZWNEWS_URL}/news/userArticleWriteForm.html?mode=input"

# Section codes for Bizwnews
SECTION_1ST_CODE = "S1N2"   # 비즈니스
SECTION_2ND_CODE = "S2N26"  # 핫이슈


class BizwnewsUploader(PlatformUploader):
    """
    Bizwnews (비즈월드) platform automated uploader.

    Same CMS as Golftimes. Key differences:
    - Different base URL (bizwnews.com)
    - Different section codes (S1N2/S2N26)
    - Submit button: button.success.expanded.large (vs btn-save)
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
        # options.add_argument("--single-process")  # Causes crash on Windows

        chromium_path = shutil.which('chromium')
        if chromium_path:
            options.binary_location = chromium_path

        for attempt in range(max_retries):
            try:
                driver = webdriver.Chrome(options=options)
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
        Login to Bizwnews platform.

        Uses /member/login.html (same CMS as Golftimes).
        """
        try:
            if self._driver is None:
                self._driver = self._get_chrome_driver()
                if self._driver is None:
                    return False

            self._driver.get(BIZWNEWS_LOGIN_URL)
            time.sleep(2)

            user_id = self.config.get_credential('id', '')
            user_pw = self.config.get_credential('pw', '')

            # Same CMS: text/password inputs without name attributes
            text_inputs = self.wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//input[@type='text']"))
            )
            id_input = text_inputs[0]
            id_input.clear()
            id_input.send_keys(user_id)

            pw_inputs = self._driver.find_elements(By.XPATH, "//input[@type='password']")
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
                print("Bizwnews login failed: could not find login button")
                return False

            time.sleep(3)
            self._handle_alert()

            self._is_logged_in = True
            return True

        except Exception as e:
            print(f"Bizwnews login failed: {e}")
            return False

    def _handle_alert(self) -> None:
        """Safely handle any browser alerts."""
        try:
            alert = self._driver.switch_to.alert
            alert.accept()
        except Exception:
            pass

    def _input_content_via_ckeditor(self, content: str) -> bool:
        """Input content using CKEditor, preserving [비즈월드] header/footer."""
        import re
        try:
            # 1. 기존 CKEditor 내용 가져오기 (헤더/푸터 포함)
            existing = self._driver.execute_script(
                "return CKEDITOR.instances['FCKeditor1'].getData();"
            )

            # 2. 본문 HTML 생성
            lines = content.split('\n')
            html_paragraphs = [f"<p>{line.strip()}</p>" for line in lines if line.strip()]
            new_html = ''.join(html_paragraphs) if html_paragraphs else f"<p>{content}</p>"

            # 3. 헤더/푸터 사이에 본문 삽입 (DOTALL 제거 - 단일 <p> 태그 내에서만 매칭)
            header_match = re.search(r'(<p[^>]*>\s*\[비즈월드\]\s*</p>)', existing)
            footer_match = re.search(r'(<p[^>]*>\s*\[비즈월드=.*?</p>)', existing)

            if header_match and footer_match:
                header = existing[:header_match.end()]
                footer = existing[footer_match.start():]
                final_html = header + new_html + footer
            else:
                final_html = new_html

            # 4. CKEditor에 설정
            js_script = f"CKEDITOR.instances['FCKeditor1'].setData({json.dumps(final_html)});"
            self._driver.execute_script(js_script)

            return True
        except Exception:
            return False

    def _click_submit_button(self) -> bool:
        """Click the submit button to publish article."""
        # Bizwnews uses: <button type="submit" class="button success expanded large">저장</button>
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
        Upload article to Bizwnews.

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

            self._driver.get(BIZWNEWS_WRITE_URL)
            time.sleep(2)

            # Select 1st section
            section1_select = Select(self._driver.find_element(By.NAME, "sectionCode"))
            section1_select.select_by_value(SECTION_1ST_CODE)
            time.sleep(1)

            # Select 2nd section
            section2_select = Select(self._driver.find_element(By.NAME, "subSectionCode"))
            section2_select.select_by_value(SECTION_2ND_CODE)

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
                print("✅ 비즈월드 기사 제출 완료")
            else:
                print("⏸️ 비즈월드 입력 완료 (제출하지 않음)")

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
    def from_config(cls, config_dict: Dict[str, Any]) -> 'BizwnewsUploader':
        """Create BizwnewsUploader from config dictionary."""
        if 'bizwnews' in config_dict:
            bw_config = config_dict['bizwnews']
        else:
            bw_config = config_dict

        bw_id = (
            bw_config.get('bizwnews_id') or
            bw_config.get('site_id') or
            os.environ.get('BIZWNEWS_ID', '')
        )
        bw_pw = (
            bw_config.get('bizwnews_pw') or
            bw_config.get('site_pw') or
            os.environ.get('BIZWNEWS_PW', '')
        )

        config = PlatformConfig(
            platform_name="bizwnews",
            login_url=BIZWNEWS_LOGIN_URL,
            write_url=BIZWNEWS_WRITE_URL,
            credentials={"id": bw_id, "pw": bw_pw},
            enabled=bw_config.get('enabled', True),
            timeout=bw_config.get('timeout', 120),
            headless=bw_config.get('headless', True),
            extra_params={
                'headless': bw_config.get('headless', True),
            }
        )

        return cls(config)


def upload_to_bizwnews(title: str, content: str,
                       config: Optional[Dict[str, Any]] = None,
                       submit: bool = False) -> UploadResult:
    """Convenience function for single upload to Bizwnews."""
    if config is None:
        config = {}

    uploader = BizwnewsUploader.from_config({'bizwnews': config})

    try:
        result = uploader.upload(title, content, submit=submit)
        return result
    finally:
        uploader.close()
