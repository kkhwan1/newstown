# -*- coding: utf-8 -*-
"""
Golftimes Platform Uploader

@TASK T8 - 플랫폼 업로더 추상화 (Golftimes 구현)
@SPEC docs/planning/02-trd.md#Golftimes-Uploader

Golftimes (thegolftimes.co.kr) automated article uploader.
"""
import time
import traceback
import os
import json
import shutil
from typing import Optional, Dict, Any, TYPE_CHECKING

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .base import PlatformUploader, UploadResult, UploadStatus, PlatformConfig


# Golftimes URL Constants
GOLFTIMES_URL = "https://www.thegolftimes.co.kr"

# User/member URLs (mode='user', default)
GOLFTIMES_LOGIN_URL = f"{GOLFTIMES_URL}/member/login.html"
GOLFTIMES_WRITE_URL = f"{GOLFTIMES_URL}/news/userArticleWriteForm.html?mode=input"

# Admin URLs (mode='admin')
GOLFTIMES_ADMIN_LOGIN_URL = f"{GOLFTIMES_URL}/admin/adminLoginForm.html"
GOLFTIMES_ADMIN_MAIN_URL = f"{GOLFTIMES_URL}/edit/adminMain.html"
GOLFTIMES_ADMIN_WRITE_URL = f"{GOLFTIMES_URL}/news/adminArticleWriteForm.html?mode=input"

# Section codes for Golftimes
SECTION_1ST_CODE = "S1N5"  # Culture section (문화)
SECTION_2ND_CODE = "S2N28"  # Hot Issues section (핫이슈)

# Default credentials (must be provided via config or environment)
DEFAULT_GOLFTIMES_ID = ""
DEFAULT_GOLFTIMES_PW = ""


class GolftimesUploader(PlatformUploader):
    """
    Golftimes platform automated uploader.

    Features:
    - Automated login with credential management
    - CKEditor JavaScript-based content input
    - Timeout protection for long-running uploads
    - Alert handling for post-upload confirmation
    """

    def __init__(self, config: PlatformConfig):
        """
        Initialize Golftimes uploader.

        Args:
            config: PlatformConfig with Golftimes settings
        """
        super().__init__(config)
        self.wait: Optional[WebDriverWait] = None

    def _get_chrome_driver(self, max_retries: int = 3):
        """
        Initialize ChromeDriver with retry logic.

        Args:
            max_retries: Maximum number of initialization attempts

        Returns:
            WebDriver instance or None if all retries fail
        """
        options = webdriver.ChromeOptions()

        if self.config.headless:
            options.add_argument("--headless")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--single-process")

        # Try to find chromium in PATH (for Replit-like environments)
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
        Login to Golftimes platform.

        Supports two modes via config extra_params:
        - mode='user' (default): Uses /member/login.html
        - mode='admin': Uses /admin/adminLoginForm.html

        Returns:
            bool: True if login successful
        """
        try:
            if self._driver is None:
                self._driver = self._get_chrome_driver()
                if self._driver is None:
                    return False

            # Select login URL based on mode
            mode = self.config.extra_params.get('mode', 'user')
            login_url = GOLFTIMES_LOGIN_URL if mode == 'user' else GOLFTIMES_ADMIN_LOGIN_URL
            self._driver.get(login_url)
            time.sleep(2)

            # Enter credentials
            user_id = self.config.get_credential('id', DEFAULT_GOLFTIMES_ID)
            user_pw = self.config.get_credential('pw', DEFAULT_GOLFTIMES_PW)

            # Both login forms use text/password inputs without name attributes
            # First text input is ID, first password input is PW
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

            # Click login button - mode-specific selectors
            login_clicked = False
            if mode == 'admin':
                # Admin form uses input[type='image'] as login button
                selectors = [
                    "//input[@type='image']",
                    "//button[@type='submit']",
                    "//input[@type='submit']",
                ]
            else:
                # User form uses <button class="... user-bg ...">로그인</button>
                # with onclick="javascript:loginform.checkLogin();return false;"
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

            # Final fallback: execute login JS function directly
            if not login_clicked:
                try:
                    if mode == 'user':
                        self._driver.execute_script("loginform.checkLogin();")
                    else:
                        self._driver.execute_script(
                            "document.querySelector('form').submit();"
                        )
                    login_clicked = True
                except Exception:
                    pass

            if not login_clicked:
                print(f"Golftimes login failed: could not find login button (mode={mode})")
                return False

            time.sleep(3)

            # Handle any alert dialogs
            self._handle_alert()

            self._is_logged_in = True
            return True

        except Exception as e:
            print(f"Golftimes login failed: {e}")
            return False

    def _handle_alert(self) -> None:
        """Safely handle any browser alerts."""
        try:
            alert = self._driver.switch_to.alert
            alert.accept()
        except Exception:
            pass

    def _input_content_via_ckeditor(self, content: str) -> bool:
        """
        Input content using CKEditor JavaScript API.

        Args:
            content: Article content to insert

        Returns:
            bool: True if content input successful
        """
        try:
            # 스프레드시트 원본 형식 보존: \n\n은 문단 구분, 각 문단은 <p> 태그로 감싸기
            paragraphs = content.split('\n\n')
            html_content = '</p><p>'.join(p.strip() for p in paragraphs if p.strip())
            html_content = f"<p>{html_content}</p>"

            # CKEditor JavaScript API로 내용 입력
            js_script = f"CKEDITOR.instances['FCKeditor1'].setData({json.dumps(html_content)});"
            self._driver.execute_script(js_script)

            return True

        except Exception:
            return False

    def _click_submit_button(self) -> bool:
        """
        Click the submit button to publish article.

        Mode-aware:
        - admin: Uses newsWriteFormSubmit() JS function or <a> link
        - user: Uses <button type="submit" class="btn btn-save"> or form.submit()

        Returns:
            bool: True if button click successful
        """
        mode = self.config.extra_params.get('mode', 'user')

        if mode == 'admin':
            return self._click_submit_button_admin()
        else:
            return self._click_submit_button_user()

    def _click_submit_button_admin(self) -> bool:
        """Submit button logic for admin mode."""
        try:
            submit_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='newsWriteFormSubmit']"))
            )
            submit_btn.click()
            return True
        except Exception:
            pass

        try:
            submit_btn = self._driver.find_element(By.XPATH, "//a[contains(text(), '등록')]")
            submit_btn.click()
            return True
        except Exception:
            pass

        try:
            self._driver.execute_script("newsWriteFormSubmit(document.newsWriteForm);")
            return True
        except Exception:
            pass

        return False

    def _click_submit_button_user(self) -> bool:
        """Submit button logic for user mode."""
        # User write form has: <button type="submit" class="btn btn-save">저장하기</button>
        try:
            submit_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-save"))
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
            # Final fallback: submit the form directly via JS
            self._driver.execute_script("document.newsWriteForm.submit();")
            return True
        except Exception:
            pass

        return False

    def upload(self, title: str, content: str, category: Optional[str] = None, submit: bool = False) -> UploadResult:
        """
        Upload article to Golftimes.

        Supports two modes via config extra_params:
        - mode='user' (default): Uses /news/userArticleWriteForm.html
        - mode='admin': Uses /news/adminArticleWriteForm.html

        Args:
            title: Article title
            content: Article body content
            category: Optional category (not used in Golftimes section selection)
            submit: If False, only fill form without submitting (default: False)

        Returns:
            UploadResult with success status and error details
        """
        try:
            # Initialize driver if needed
            if self._driver is None:
                self._driver = self._get_chrome_driver()
                if self._driver is None:
                    return UploadResult(
                        success=False,
                        platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="ChromeDriver initialization failed"
                    )

            # Login if not already logged in
            if not self._is_logged_in:
                if not self.login():
                    return UploadResult(
                        success=False,
                        platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="Login failed"
                    )

            # Navigate to write page based on mode
            mode = self.config.extra_params.get('mode', 'user')
            write_url = GOLFTIMES_WRITE_URL if mode == 'user' else GOLFTIMES_ADMIN_WRITE_URL
            self._driver.get(write_url)
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

            # Select writer - only available in admin mode
            # User mode auto-fills writer from logged-in user profile
            if mode == 'admin':
                try:
                    self._driver.execute_script(
                        "writerSet('tymedia', '김한솔', 'master@thegolftimes.co.kr', '기자');"
                    )
                    print("작성자 '김한솔' 선택 완료 (admin)")
                except Exception as e:
                    print(f"작성자 선택 실패 (계속 진행): {e}")

            # Enter content via CKEditor
            if not self._input_content_via_ckeditor(content):
                return UploadResult(
                    success=False,
                    platform=self.platform_name,
                    status=UploadStatus.FAILED,
                    error_message="Failed to input content via CKEditor"
                )

            # Optionally click submit button (default: False - don't submit)
            if submit:
                # Small delay to ensure all data is set
                time.sleep(2)

                if not self._click_submit_button():
                    return UploadResult(
                        success=False,
                        platform=self.platform_name,
                        status=UploadStatus.FAILED,
                        error_message="Failed to click submit button"
                    )
                time.sleep(5)
                # Handle post-upload alert
                self._handle_alert()
                print("✅ 기사 제출 완료")
            else:
                # Form filled, waiting for manual submission
                print("⏸️ 입력 완료 (제출하지 않음)")

            return UploadResult(
                success=True,
                platform=self.platform_name,
                status=UploadStatus.SUCCESS,
                metadata={"title_length": len(title), "submitted": submit}
            )

        except Exception as e:
            return UploadResult(
                success=False,
                platform=self.platform_name,
                status=UploadStatus.FAILED,
                error_message=str(e)
            )

    def logout(self) -> bool:
        """
        Logout from Golftimes.

        Returns:
            bool: True if logout successful
        """
        self._is_logged_in = False
        return True

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'GolftimesUploader':
        """
        Create GolftimesUploader from config dictionary.

        Args:
            config_dict: Dictionary with platform config. Can be either:
                - {'golftimes': {...}}  (wrapped format)
                - {...} (direct format with golftimes_id, golftimes_pw keys)

        Returns:
            Configured GolftimesUploader instance
        """
        # Handle both {'golftimes': {...}} and direct {...} formats
        if 'golftimes' in config_dict:
            golftimes_config = config_dict['golftimes']
        else:
            golftimes_config = config_dict

        # Get credentials from config (with environment variable fallback)
        # Priority: config value > environment variable > default
        gt_id = (
            golftimes_config.get('golftimes_id') or
            golftimes_config.get('site_id') or
            os.environ.get('GOLFTIMES_ID') or
            DEFAULT_GOLFTIMES_ID
        )
        gt_pw = (
            golftimes_config.get('golftimes_pw') or
            golftimes_config.get('site_pw') or
            os.environ.get('GOLFTIMES_PW') or
            DEFAULT_GOLFTIMES_PW
        )

        # Determine mode and select URLs accordingly
        mode = golftimes_config.get('mode', 'user')
        login_url = GOLFTIMES_LOGIN_URL if mode == 'user' else GOLFTIMES_ADMIN_LOGIN_URL
        write_url = GOLFTIMES_WRITE_URL if mode == 'user' else GOLFTIMES_ADMIN_WRITE_URL

        config = PlatformConfig(
            platform_name="golftimes",
            login_url=login_url,
            write_url=write_url,
            credentials={"id": gt_id, "pw": gt_pw},
            enabled=golftimes_config.get('enabled', True),
            timeout=golftimes_config.get('timeout', 120),
            headless=golftimes_config.get('headless', True),
            extra_params={
                'mode': mode,
                'headless': golftimes_config.get('headless', True),
            }
        )

        return cls(config)

    @classmethod
    def from_process_config(cls, process_config: Dict[str, Any]) -> 'GolftimesUploader':
        """
        Create GolftimesUploader from process config (environment variable style).

        Args:
            process_config: Process configuration dict with 'golftimes_id', 'golftimes_pw' keys

        Returns:
            Configured GolftimesUploader instance
        """
        gt_id = process_config.get('golftimes_id', DEFAULT_GOLFTIMES_ID)
        gt_pw = process_config.get('golftimes_pw', DEFAULT_GOLFTIMES_PW)
        mode = process_config.get('mode', 'user')
        login_url = GOLFTIMES_LOGIN_URL if mode == 'user' else GOLFTIMES_ADMIN_LOGIN_URL
        write_url = GOLFTIMES_WRITE_URL if mode == 'user' else GOLFTIMES_ADMIN_WRITE_URL

        config = PlatformConfig(
            platform_name="golftimes",
            login_url=login_url,
            write_url=write_url,
            credentials={"id": gt_id, "pw": gt_pw},
            enabled=True,
            timeout=120,
            headless=True,
            extra_params={
                'mode': mode,
            }
        )

        return cls(config)


def upload_to_golftimes(title: str, content: str,
                        config: Optional[Dict[str, Any]] = None,
                        submit: bool = False) -> UploadResult:
    """
    Convenience function for single upload to Golftimes.

    Args:
        title: Article title
        content: Article content
        config: Optional configuration dict
        submit: If False, only fill form without submitting (default: False)

    Returns:
        UploadResult with upload status
    """
    if config is None:
        config = {}

    uploader = GolftimesUploader.from_config({'golftimes': config})

    try:
        result = uploader.upload(title, content, submit=submit)
        return result
    finally:
        uploader.close()
