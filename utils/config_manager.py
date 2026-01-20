# -*- coding: utf-8 -*-
"""
설정 관리 모듈
PostgreSQL 기반 설정 영속화 및 기본값 관리
배포 환경에서도 설정이 유지됨
"""
import copy
import json
import os
from typing import Any, Dict, Optional, Union
from pathlib import Path

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    load_dotenv = None
    DOTENV_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class ConfigManager:
    """PostgreSQL 기반 설정 관리 클래스"""

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
        "newstown": {
            "site_id": "",
            "site_pw": ""
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
        "golftimes": {
            "site_id": "thegolftimes",
            "site_pw": "Golf1220"
        },
        "upload_platforms": {
            "newstown": {
                "enabled": True,
                "title_column": 5,
                "content_column": 6,
                "completed_column": 8
            },
            "golftimes": {
                "enabled": False,
                "title_column": 10,
                "content_column": 11,
                "completed_column": 12
            }
        }
    }

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """설정 관리자 초기화"""
        base_dir = Path(__file__).parent.parent
        self.config_path = base_dir / "config" / "dashboard_config.json"
        self._config: Dict[str, Any] = {}
        self._db_url = os.environ.get('DATABASE_URL')
        
        self._load_env(base_dir)
        self._ensure_table()
        self._load()
        self._apply_env_overrides()

    def _get_connection(self):
        """DB 연결 반환"""
        if not PSYCOPG2_AVAILABLE or not self._db_url:
            return None
        try:
            return psycopg2.connect(self._db_url)
        except Exception as e:
            print(f"⚠️ DB 연결 실패: {e}")
            return None

    def _ensure_table(self):
        """settings 테이블 존재 확인"""
        conn = self._get_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        id SERIAL PRIMARY KEY,
                        key VARCHAR(255) UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"⚠️ 테이블 생성 실패: {e}")
        finally:
            conn.close()

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

    def _apply_env_overrides(self):
        """환경 변수로 설정 오버라이드"""
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if sheet_url:
            self._config.setdefault("google_sheet", {})
            self._config["google_sheet"]["url"] = sheet_url

        newstown_id = os.getenv("NEWSTOWN_ID")
        if newstown_id:
            self._config.setdefault("newstown", {})
            self._config["newstown"]["site_id"] = newstown_id
        newstown_pw = os.getenv("NEWSTOWN_PW")
        if newstown_pw:
            self._config.setdefault("newstown", {})
            self._config["newstown"]["site_pw"] = newstown_pw

        naver_id = os.getenv("NAVER_CLIENT_ID")
        if naver_id:
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_id"] = naver_id
        naver_secret = os.getenv("NAVER_CLIENT_SECRET")
        if naver_secret:
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_secret"] = naver_secret

    def _load_from_db(self) -> Dict[str, Any]:
        """DB에서 설정 로드"""
        conn = self._get_connection()
        if not conn:
            return {}
        
        config = {}
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM settings")
                rows = cur.fetchall()
                for key, value in rows:
                    try:
                        config[key] = json.loads(value)
                    except json.JSONDecodeError:
                        config[key] = value
            if config:
                print(f"✅ DB에서 설정 로드됨: {len(config)}개 섹션")
        except Exception as e:
            print(f"⚠️ DB 설정 로드 실패: {e}")
        finally:
            conn.close()
        return config

    def _save_to_db(self, section: str, data: Any) -> bool:
        """DB에 설정 저장"""
        conn = self._get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                value = json.dumps(data, ensure_ascii=False)
                cur.execute("""
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) 
                    DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (section, value))
                conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ DB 설정 저장 실패: {e}")
            return False
        finally:
            conn.close()

    def _load(self):
        """설정 로드 (DB 우선, 없으면 JSON 파일 또는 기본값)"""
        db_config = self._load_from_db()
        
        if db_config:
            self._config = db_config
            return
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                print(f"✅ JSON 설정 파일 로드됨: {self.config_path}")
                self._migrate_json_to_db()
            except Exception as e:
                print(f"⚠️ JSON 설정 파일 로드 실패, 기본값 사용: {e}")
                self._config = copy.deepcopy(self.DEFAULT_CONFIG)
                self._save_all_to_db()
        else:
            print(f"ℹ️ 설정이 없어 기본값으로 생성합니다.")
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            self._save_all_to_db()

    def _migrate_json_to_db(self):
        """JSON 설정을 DB로 마이그레이션"""
        print("📦 JSON 설정을 DB로 마이그레이션 중...")
        for section, data in self._config.items():
            self._save_to_db(section, data)
        print("✅ DB 마이그레이션 완료")

    def _save_all_to_db(self):
        """모든 설정을 DB에 저장"""
        for section, data in self._config.items():
            self._save_to_db(section, data)

    def _save(self, force: bool = False) -> bool:
        """설정 저장 (하위 호환성 유지)"""
        return True

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
        if section not in self._config:
            self._config[section] = {}

        self._config[section][key] = value

        if save:
            self._save_to_db(section, self._config[section])

    def set_section(self, section: str, data: Dict[str, Any], save: bool = True, force: bool = True) -> bool:
        """섹션 전체 저장"""
        self._config[section] = copy.deepcopy(data)

        if save:
            return self._save_to_db(section, data)
        return True

    def get_all(self) -> Dict[str, Any]:
        """전체 설정 반환"""
        return copy.deepcopy(self._config)

    def reset_to_default(self, section: Optional[str] = None, save: bool = True):
        """기본값으로 초기화"""
        if section is None:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            if save:
                self._save_all_to_db()
        else:
            if section in self.DEFAULT_CONFIG:
                self._config[section] = copy.deepcopy(self.DEFAULT_CONFIG[section])
                if save:
                    self._save_to_db(section, self._config[section])

    def reload(self):
        """설정 다시 로드 (DB에서)"""
        db_config = self._load_from_db()
        if db_config:
            self._config = db_config

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
        config['site_id'] = self.get("newstown", "site_id")
        config['site_pw'] = self.get("newstown", "site_pw")
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

    def get_all_upload_config(self) -> Dict[str, Any]:
        """업로드 관련 전체 설정 반환 (뉴스타운 + 골프타임즈)"""
        base_config = self.get("upload_monitor")
        base_config['sheet_url'] = self.get("google_sheet", "url")
        base_config['site_id'] = self.get("newstown", "site_id")
        base_config['site_pw'] = self.get("newstown", "site_pw")
        base_config['golftimes_id'] = self.get("golftimes", "site_id")
        base_config['golftimes_pw'] = self.get("golftimes", "site_pw")
        base_config['platforms'] = self.get("upload_platforms")
        return base_config


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
