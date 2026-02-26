# -*- coding: utf-8 -*-
"""
Platform Uploader Abstract Base Class

@TASK T8 - 플랫폼 업로더 추상화
@SPEC docs/planning/02-trd.md#Platform-Abstraction

All platform uploaders must inherit from PlatformUploader ABC.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class UploadStatus(Enum):
    """Upload status enumeration"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class UploadResult:
    """
    Result dataclass for platform upload operations.

    Attributes:
        success: Whether the upload was successful
        platform: Platform name (e.g., 'golftimes')
        status: Detailed upload status
        error_message: Error message if upload failed
        uploaded_at: Timestamp of upload attempt
        metadata: Additional platform-specific metadata
    """
    success: bool
    platform: str
    status: UploadStatus = UploadStatus.PENDING
    error_message: Optional[str] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        if self.success:
            return f"UploadResult(success=True, platform={self.platform}, status={self.status.value})"
        return f"UploadResult(success=False, platform={self.platform}, error={self.error_message})"


@dataclass
class PlatformConfig:
    """
    Platform configuration dataclass.

    Attributes:
        platform_name: Unique platform identifier
        login_url: URL for login page
        write_url: URL for article write page
        credentials: Dict with 'id' and 'pw' keys
        enabled: Whether this platform is active
        timeout: Upload timeout in seconds
        headless: Run browser in headless mode
    """
    platform_name: str
    login_url: str
    write_url: str
    credentials: Dict[str, str]
    enabled: bool = True
    timeout: int = 120
    headless: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def get_credential(self, key: str, default: str = "") -> str:
        """Safely get a credential value"""
        return self.credentials.get(key, default)


class PlatformUploader(ABC):
    """
    Abstract base class for platform uploaders.

    All platform-specific uploaders must implement these methods:
    - login(): Authenticate with the platform
    - upload(): Upload content with title and body
    - logout(): End the session (optional cleanup)

    Driver pooling is managed by the DriverPool class to reuse
    browser instances across multiple uploads.
    """

    def __init__(self, config: PlatformConfig):
        """
        Initialize the uploader with platform configuration.

        Args:
            config: PlatformConfig instance with platform settings
        """
        self.config = config
        self.platform_name = config.platform_name
        self._driver = None
        self._is_logged_in = False

    @property
    def driver(self):
        """Get the current WebDriver instance"""
        return self._driver

    @driver.setter
    def driver(self, value):
        """Set the WebDriver instance"""
        self._driver = value

    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in"""
        return self._is_logged_in

    @abstractmethod
    def login(self) -> bool:
        """
        Authenticate with the platform.

        Returns:
            bool: True if login successful, False otherwise
        """
        pass

    @abstractmethod
    def upload(self, title: str, content: str, category: Optional[str] = None) -> UploadResult:
        """
        Upload content to the platform.

        Args:
            title: Article title
            content: Article body/content
            category: Optional category for classification

        Returns:
            UploadResult: Result object with success status and error details
        """
        pass

    def logout(self) -> bool:
        """
        End the session and perform cleanup.

        Default implementation performs basic cleanup.
        Override if platform requires specific logout actions.

        Returns:
            bool: True if logout successful, False otherwise
        """
        self._is_logged_in = False
        return True

    def close(self) -> None:
        """
        Close the browser driver.

        Safe to call multiple times.
        """
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._driver = None
                self._is_logged_in = False

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.close()
        return False

    @classmethod
    @abstractmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'PlatformUploader':
        """
        Factory method to create uploader from config dictionary.

        Args:
            config_dict: Dictionary with platform configuration

        Returns:
            PlatformUploader: Configured uploader instance
        """
        pass
