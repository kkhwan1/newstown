# -*- coding: utf-8 -*-
"""
설정 관리 모듈
JSON 파일 기반 설정 영속화 및 기본값 관리

@TASK T7 - Pydantic 검증 추가
@SPEC CLAUDE.md#Configuration
"""
import copy
import json
import os
import threading
from typing import Any, Dict, Optional, Union, Tuple
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    load_dotenv = None
    DOTENV_AVAILABLE = False

try:
    from .config_schema import (
        AppConfig,
        validate_config_dict,
        validate_section,
        NewsCollectionConfig,
        PlatformCredentials,
        NaverApiConfig,
        GoogleSheetConfig,
        UploadMonitorConfig,
        PlatformConfig,
    )
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class ConfigManager:
    """JSON 파일 기반 설정 관리 클래스"""

    @staticmethod
    def _create_default_config() -> Dict[str, Any]:
        """기본 설정 생성 (Pydantic 모델 기반)"""
        if PYDANTIC_AVAILABLE:
            default_model = AppConfig()
            return default_model.model_dump()
        return {
            "news_collection": {
                "keywords": {"연애": 15, "경제": 15, "스포츠": 15},
                "display_count": 30,
                "max_workers": 10,
                "sort": "date"
            },
            "category_keywords": {
                "연애": {
                    "core": ["연애", "열애", "커플", "결혼", "고백"],
                    "general": ["신랑", "신부", "웨딩", "혼수"]
                },
                "경제": {
                    "core": ["경제", "증시", "코스피", "코스닥", "나스닥"],
                    "general": ["은행", "금융", "증권"]
                },
                "스포츠": {
                    "core": ["스포츠", "야구", "축구", "농구", "배구"],
                    "general": ["선수", "감독", "코치"]
                }
            },
            "upload_monitor": {
                "check_interval": 30,
                "completed_column": 8,
                "concurrent_uploads": 1
            },
            "row_deletion": {
                "delete_interval": 60,
                "max_delete_count": 10
            },
            "google_sheet": {
                "url": ""
            },
            "naver_api": {
                "client_id": "",
                "client_secret": ""
            },
            "news_schedule": {
                "enabled": False,
                "interval_hours": 3,
                "last_run": None
            },
            # @SECURITY A05 - 하드코딩된 비밀번호 제거
            "golftimes": {
                "site_id": "thegolftimes",
                "site_pw": ""
            },
            "upload_platforms": {
                "golftimes": {
                    "enabled": False,
                    "display_name": "골프타임즈",
                    "title_column": 10,
                    "content_column": 11,
                    "completed_column": 12,
                    "credentials_section": "golftimes"
                }
            }
        }

    DEFAULT_CONFIG = {
        "news_collection": {
            "keywords": {"연애": 15, "경제": 15, "스포츠": 15},
            "display_count": 30,
            "max_workers": 10,
            "sort": "date"
        },
        "category_keywords": {
            "연애": {
                "core": ["연애", "열애", "커플", "결혼", "고백"],
                "general": ["신랑", "신부", "웨딩", "혼수"]
            },
            "경제": {
                "core": ["경제", "증시", "코스피", "코스닥", "나스닥"],
                "general": ["은행", "금융", "증권"]
            },
            "스포츠": {
                "core": ["스포츠", "야구", "축구", "농구", "배구"],
                "general": ["선수", "감독", "코치"]
            }
        },
        "upload_monitor": {
            "check_interval": 30,
            "completed_column": 8,
            "concurrent_uploads": 1
        },
        "row_deletion": {
            "delete_interval": 60,
            "max_delete_count": 10
        },
        "google_sheet": {
            "url": ""
        },
        "naver_api": {
            "client_id": "",
            "client_secret": ""
        },
        "news_schedule": {
            "enabled": False,
            "interval_hours": 3,
            "last_run": None
        },
        # @SECURITY A05 - 하드코딩된 비밀번호 제거
        "golftimes": {
            "site_id": "thegolftimes",
            "site_pw": ""
        },
        "upload_platforms": {
            "golftimes": {
                "enabled": False,
                "display_name": "골프타임즈",
                "title_column": 10,
                "content_column": 11,
                "completed_column": 12,
                "credentials_section": "golftimes"
            }
        }
    }

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """설정 관리자 초기화"""
        base_dir = Path(__file__).parent.parent
        self.config_path = base_dir / "config" / "dashboard_config.json"
        self._config: Dict[str, Any] = {}
        self._lock = threading.Lock()

        self._load_env(base_dir)
        self._load()
        self._apply_env_overrides()

    def _load_env(self, base_dir: Path):
        """.env 파일 로드"""
        if not DOTENV_AVAILABLE or load_dotenv is None:
            return
        env_path = base_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ .env 파일 로드됨: {env_path}")
        else:
            print(f"ℹ️ .env 파일이 없습니다. 기본 설정을 사용합니다.")

    @staticmethod
    def _validate_url(url: str) -> bool:
        """URL 유효성 검증 (http/https 스킴만 허용)"""
        try:
            result = urlparse(url)
            return result.scheme in ('http', 'https') and bool(result.netloc)
        except Exception:
            return False

    def _apply_env_overrides(self):
        """환경 변수로 설정 오버라이드"""
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if sheet_url:
            if self._validate_url(sheet_url):
                self._config.setdefault("google_sheet", {})
                self._config["google_sheet"]["url"] = sheet_url
            else:
                print(f"Warning: GOOGLE_SHEET_URL 환경 변수의 URL이 유효하지 않아 무시됨: {sheet_url}")

        naver_id = os.getenv("NAVER_CLIENT_ID")
        if naver_id:
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_id"] = naver_id
        naver_secret = os.getenv("NAVER_CLIENT_SECRET")
        if naver_secret:
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_secret"] = naver_secret

    def _load(self):
        """설정 로드 (JSON 파일 또는 기본값)"""
        self._config = copy.deepcopy(self.DEFAULT_CONFIG)
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                # Merge: file values override defaults
                for section, data in file_config.items():
                    if isinstance(data, dict) and isinstance(self._config.get(section), dict):
                        self._config[section].update(data)
                    else:
                        self._config[section] = data
                print(f"✅ JSON 설정 파일 로드됨: {self.config_path}")
            except Exception as e:
                print(f"⚠️ JSON 설정 파일 로드 실패, 기본값 사용: {e}")
        else:
            print(f"ℹ️ 설정이 없어 기본값으로 생성합니다.")
            self._save_to_json()

    def _save_to_json(self) -> bool:
        """JSON 파일에 설정 저장"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ JSON 설정 저장 실패: {e}")
            return False

    # ========== Pydantic 검증 메서드 ==========

    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        전체 설정 Pydantic 검증

        Returns:
            (검증성공, 에러메시지)
        """
        if not PYDANTIC_AVAILABLE:
            return True, None

        success, error_msg, _ = validate_config_dict(self._config)
        return success, error_msg

    def validate_section(self, section_name: str) -> Tuple[bool, Optional[str]]:
        """
        특정 섹션 Pydantic 검증

        Returns:
            (검증성공, 에러메시지)
        """
        if not PYDANTIC_AVAILABLE:
            return True, None

        section_data = self._config.get(section_name)
        if section_data is None:
            return False, f"섹션을 찾을 수 없습니다: {section_name}"

        success, error_msg, _ = validate_section(section_name, section_data)
        return success, error_msg

    def set_with_validation(self, section: str, key: str, value: Any, save: bool = True) -> Tuple[bool, Optional[str]]:
        """
        설정 값 저장 (Pydantic 검증 포함)

        Returns:
            (성공여부, 에러메시지)
        """
        if section not in self._config:
            self._config[section] = {}

        self._config[section][key] = value

        # Pydantic 검증
        if PYDANTIC_AVAILABLE:
            success, error_msg = self.validate_section(section)
            if not success:
                # 실패 시 롤백
                if key in self._config[section]:
                    del self._config[section][key]
                return False, error_msg

        if save:
            self._save_to_json()

        return True, None

    def set_section_with_validation(self, section: str, data: Dict[str, Any], save: bool = True) -> Tuple[bool, Optional[str]]:
        """
        섹션 전체 저장 (Pydantic 검증 포함)

        Returns:
            (성공여부, 에러메시지)
        """
        # 임시로 데이터 설정하여 검증
        original_data = self._config.get(section, {})
        self._config[section] = copy.deepcopy(data)

        # Pydantic 검증
        if PYDANTIC_AVAILABLE:
            success, error_msg = self.validate_section(section)
            if not success:
                # 실패 시 롤백
                self._config[section] = original_data
                return False, error_msg

        if save:
            result = self._save_to_json()
            return result, None if result else "Failed to save to JSON"

        return True, None

    def get_pydantic_model(self, section: Optional[str] = None) -> Any:
        """
        Pydantic 모델 인스턴스 반환

        Args:
            section: None이면 전체 AppConfig, 특정 섹션 이름이면 해당 모델

        Returns:
            Pydantic 모델 인스턴스 또는 None
        """
        if not PYDANTIC_AVAILABLE:
            return None

        try:
            if section is None:
                return AppConfig(**self._config)

            model_map = {
                "news_collection": NewsCollectionConfig,
                "upload_monitor": UploadMonitorConfig,
                "google_sheet": GoogleSheetConfig,
                "naver_api": NaverApiConfig,
            }

            model_class = model_map.get(section)
            if model_class and section in self._config:
                return model_class(**self._config[section])

        except Exception as e:
            print(f"⚠️ Pydantic 모델 생성 실패: {e}")

        return None

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """설정 값 조회"""
        section_data = self._config.get(section, self.DEFAULT_CONFIG.get(section, {}))

        if key is None:
            return copy.deepcopy(section_data)

        if key in section_data:
            value = section_data[key]
            if isinstance(value, (dict, list)):
                return copy.deepcopy(value)
            return value

        default_section = self.DEFAULT_CONFIG.get(section, {})
        value = default_section.get(key, default)
        if isinstance(value, (dict, list)):
            return copy.deepcopy(value)
        return value

    def set(self, section: str, key: str, value: Any, save: bool = True):
        """설정 값 저장"""
        with self._lock:
            if section not in self._config:
                self._config[section] = {}

            self._config[section][key] = value

        if save:
            self._save_to_json()

    def set_section(self, section: str, data: Dict[str, Any], save: bool = True, force: bool = True) -> bool:
        """섹션 전체 저장"""
        with self._lock:
            self._config[section] = copy.deepcopy(data)

        if save:
            return self._save_to_json()
        return True

    def get_all(self) -> Dict[str, Any]:
        """전체 설정 반환"""
        return copy.deepcopy(self._config)

    def reset_to_default(self, section: Optional[str] = None, save: bool = True):
        """기본값으로 초기화"""
        if section is None:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            if save:
                self._save_to_json()
        else:
            if section in self.DEFAULT_CONFIG:
                self._config[section] = copy.deepcopy(self.DEFAULT_CONFIG[section])
                if save:
                    self._save_to_json()

    def reload(self):
        """설정 다시 로드 (JSON에서)"""
        self._load()
        self._apply_env_overrides()

    def get_news_config(self) -> Dict[str, Any]:
        """뉴스 수집 설정 반환"""
        config = self.get("news_collection")
        config['sheet_url'] = self.get("google_sheet", "url")
        config['naver_client_id'] = self.get("naver_api", "client_id")
        config['naver_client_secret'] = self.get("naver_api", "client_secret")
        config['category_keywords'] = self.get("category_keywords") or {}
        return config

    def get_upload_config(self) -> Dict[str, Any]:
        """업로드 감시 설정 반환"""
        config = self.get("upload_monitor")
        config['sheet_url'] = self.get("google_sheet", "url")
        return config

    def get_deletion_config(self) -> Dict[str, Any]:
        """행 삭제 설정 반환"""
        config = self.get("row_deletion")
        config['sheet_url'] = self.get("google_sheet", "url")
        config['completed_column'] = self.get("upload_monitor", "completed_column")
        return config

    def get_golftimes_config(self) -> Dict[str, Any]:
        """골프타임즈 설정 반환"""
        config = self.get("golftimes")
        return config

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """플랫폼별 설정 반환"""
        platforms = self.get("upload_platforms")
        return platforms.get(platform, {})

    def is_platform_enabled(self, platform: str) -> bool:
        """플랫폼 활성화 여부 반환"""
        platforms = self.get("upload_platforms")
        return platforms.get(platform, {}).get("enabled", False)

    def set_platform_enabled(self, platform: str, enabled: bool, save: bool = True):
        """플랫폼 활성화 여부 설정"""
        platforms = self.get("upload_platforms")
        if platform not in platforms:
            platforms[platform] = {}
        platforms[platform]["enabled"] = enabled
        if save:
            self.set_section("upload_platforms", platforms, save=True)

    def get_all_upload_config(self, selected_platforms: Optional[list] = None) -> Dict[str, Any]:
        """업로드 관련 전체 설정 반환 (선택된 플랫폼만 포함)"""
        base_config = self.get("upload_monitor")
        base_config['sheet_url'] = self.get("google_sheet", "url")
        base_config['golftimes_id'] = self.get("golftimes", "site_id")
        base_config['golftimes_pw'] = self.get("golftimes", "site_pw")

        all_platforms = self.get("upload_platforms")
        if selected_platforms:
            base_config['platforms'] = {k: v for k, v in all_platforms.items() if k in selected_platforms}
            for p in selected_platforms:
                if p in base_config['platforms']:
                    base_config['platforms'][p]['enabled'] = True
        else:
            base_config['platforms'] = all_platforms
        return base_config

    def get_all_platforms(self) -> Dict[str, Dict[str, Any]]:
        """모든 플랫폼 목록 반환"""
        return self.get("upload_platforms") or {}

    def get_enabled_platforms(self) -> list:
        """활성화된 플랫폼 목록 반환"""
        platforms = self.get("upload_platforms") or {}
        return [k for k, v in platforms.items() if v.get("enabled", False)]

    def add_platform(self, platform_id: str, display_name: str,
                     title_column: int, content_column: int, completed_column: int,
                     credentials_section: str = None, save: bool = True) -> bool:
        """새 플랫폼 추가"""
        platforms = self.get("upload_platforms") or {}
        platforms[platform_id] = {
            "enabled": False,
            "display_name": display_name,
            "title_column": title_column,
            "content_column": content_column,
            "completed_column": completed_column,
            "credentials_section": credentials_section or platform_id
        }
        if save:
            return self.set_section("upload_platforms", platforms, save=True)
        return True

    def remove_platform(self, platform_id: str, save: bool = True) -> bool:
        """플랫폼 삭제"""
        platforms = self.get("upload_platforms") or {}
        if platform_id in platforms:
            del platforms[platform_id]
            if save:
                return self.set_section("upload_platforms", platforms, save=True)
        return True

    def update_platform(self, platform_id: str, updates: Dict[str, Any], save: bool = True) -> bool:
        """플랫폼 설정 업데이트"""
        platforms = self.get("upload_platforms") or {}
        if platform_id in platforms:
            platforms[platform_id].update(updates)
            if save:
                return self.set_section("upload_platforms", platforms, save=True)
        return False

    def get_platform_display_name(self, platform_id: str) -> str:
        """플랫폼 표시 이름 반환"""
        platforms = self.get("upload_platforms") or {}
        platform = platforms.get(platform_id, {})
        names = {"golftimes": "골프타임즈"}
        return platform.get("display_name", names.get(platform_id, platform_id))


_global_config: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """전역 설정 관리자 인스턴스 반환"""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config

def reload_config_manager():
    """설정 관리자 다시 로드"""
    global _global_config
    if _global_config:
        _global_config.reload()
    else:
        _global_config = ConfigManager()
    return _global_config
