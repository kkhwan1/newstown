# -*- coding: utf-8 -*-
"""
설정 관리 모듈
JSON 기반 설정 영속화 및 기본값 관리
.env 파일 지원으로 민감한 정보 분리
"""
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path

# python-dotenv 로드
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class ConfigManager:
    """JSON 기반 설정 관리 클래스"""

    DEFAULT_CONFIG = {
        "news_collection": {
            "keywords": {"연애": 15, "경제": 15, "스포츠": 15},
            "display_count": 30,
            "max_workers": 10
        },
        "category_keywords": {
            "연애": {
                "core": ["연애", "열애", "열애설", "커플", "결혼", "이혼", "데이트", "로맨스",
                         "사랑", "프로포즈", "청혼", "신혼", "재혼", "불륜", "바람", "이별",
                         "재회", "소개팅", "맞선", "혼인", "부부", "연인", "애인", "결별",
                         "파혼", "약혼", "동거", "외도", "썸", "고백", "짝사랑"],
                "general": ["신랑", "신부", "웨딩", "혼수", "신혼여행", "교제", "연하남",
                            "연상녀", "돌싱", "미혼", "기혼", "솔로", "커플룩", "커플링",
                            "기념일", "발렌타인", "화이트데이", "연애상담", "권태기"]
            },
            "경제": {
                "core": ["경제", "금리", "주식", "부동산", "인플레이션", "물가", "환율",
                         "증시", "코스피", "코스닥", "나스닥", "GDP", "경기침체", "불황",
                         "금융위기", "기준금리", "금리인상", "금리인하", "실적발표", "어닝쇼크"],
                "general": ["은행", "금융", "증권", "보험", "펀드", "채권", "투자", "자산",
                            "배당", "시가총액", "IPO", "상장", "ETF", "비트코인", "암호화폐",
                            "기업", "매출", "영업이익", "순이익", "실적", "CEO", "인수합병",
                            "연봉", "최저임금", "고용", "실업", "세금", "수출", "수입",
                            "반도체", "자동차", "스타트업", "벤처"]
            },
            "스포츠": {
                "core": ["스포츠", "야구", "축구", "농구", "배구", "골프", "테니스",
                         "올림픽", "월드컵", "KBO", "K리그", "프로야구", "프로축구",
                         "MLB", "NBA", "NFL", "EPL", "프리미어리그"],
                "general": ["선수", "감독", "코치", "구단", "팀", "이적", "영입", "FA",
                            "경기", "시합", "대회", "우승", "패배", "승리", "득점", "골",
                            "홈런", "안타", "MVP", "올스타", "수영", "육상", "격투기",
                            "UFC", "e스포츠", "롤드컵", "LCK"]
            }
        },
        "upload_monitor": {
            "check_interval": 30,
            "completed_column": 8
        },
        "row_deletion": {
            "delete_interval": 60,
            "max_delete_count": 10
        },
        "google_sheet": {
            "url": "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit"
        },
        "newstown": {
            "site_id": "kim123",
            "site_pw": "love1105()"
        },
        "naver_api": {
            "client_id": "hj620p2ZnD94LNjNaW8d",
            "client_secret": "sDRT5fUUaK"
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """설정 관리자 초기화

        Args:
            config_path: 설정 파일 경로 (None이면 기본 경로 사용)
        """
        # 기본 경로 설정
        base_dir = Path(__file__).parent.parent

        if config_path is None:
            config_path = base_dir / "config" / "dashboard_config.json"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}

        # .env 파일 로드
        self._load_env(base_dir)

        # JSON 설정 로드
        self._load()

        # 환경 변수로 설정 오버라이드
        self._apply_env_overrides()

    def _load_env(self, base_dir: Path):
        """.env 파일 로드"""
        if not DOTENV_AVAILABLE:
            return

        env_path = base_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ .env 파일 로드됨: {env_path}")
        else:
            print(f"ℹ️ .env 파일이 없습니다. 기본 설정을 사용합니다.")

    def _apply_env_overrides(self):
        """환경 변수로 설정 오버라이드"""
        # Google Sheet URL
        if os.getenv("GOOGLE_SHEET_URL"):
            self._config.setdefault("google_sheet", {})
            self._config["google_sheet"]["url"] = os.getenv("GOOGLE_SHEET_URL")

        # 뉴스타운 로그인 정보
        if os.getenv("NEWSTOWN_ID"):
            self._config.setdefault("newstown", {})
            self._config["newstown"]["site_id"] = os.getenv("NEWSTOWN_ID")
        if os.getenv("NEWSTOWN_PW"):
            self._config.setdefault("newstown", {})
            self._config["newstown"]["site_pw"] = os.getenv("NEWSTOWN_PW")

        # 네이버 API
        if os.getenv("NAVER_CLIENT_ID"):
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_id"] = os.getenv("NAVER_CLIENT_ID")
        if os.getenv("NAVER_CLIENT_SECRET"):
            self._config.setdefault("naver_api", {})
            self._config["naver_api"]["client_secret"] = os.getenv("NAVER_CLIENT_SECRET")

        # 뉴스 수집 설정
        if os.getenv("NEWS_DISPLAY_COUNT"):
            self._config.setdefault("news_collection", {})
            self._config["news_collection"]["display_count"] = int(os.getenv("NEWS_DISPLAY_COUNT"))
        if os.getenv("NEWS_MAX_WORKERS"):
            self._config.setdefault("news_collection", {})
            self._config["news_collection"]["max_workers"] = int(os.getenv("NEWS_MAX_WORKERS"))

        # 업로드 감시 설정
        if os.getenv("UPLOAD_CHECK_INTERVAL"):
            self._config.setdefault("upload_monitor", {})
            self._config["upload_monitor"]["check_interval"] = int(os.getenv("UPLOAD_CHECK_INTERVAL"))
        if os.getenv("UPLOAD_COMPLETED_COLUMN"):
            self._config.setdefault("upload_monitor", {})
            self._config["upload_monitor"]["completed_column"] = int(os.getenv("UPLOAD_COMPLETED_COLUMN"))

        # 완료행 삭제 설정
        if os.getenv("DELETE_INTERVAL"):
            self._config.setdefault("row_deletion", {})
            self._config["row_deletion"]["delete_interval"] = int(os.getenv("DELETE_INTERVAL"))
        if os.getenv("DELETE_MAX_COUNT"):
            self._config.setdefault("row_deletion", {})
            self._config["row_deletion"]["max_delete_count"] = int(os.getenv("DELETE_MAX_COUNT"))

    def _load(self):
        """설정 파일 로드"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                print(f"✅ 설정 파일 로드됨: {self.config_path}")
            except Exception as e:
                print(f"⚠️ 설정 파일 로드 실패, 기본값 사용: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            print(f"ℹ️ 설정 파일이 없어 기본값으로 생성합니다.")
            self._config = self.DEFAULT_CONFIG.copy()
            self._save()

    def _save(self):
        """설정 파일 저장 (변경사항이 있을 때만)"""
        try:
            # 디렉토리가 없으면 생성
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # 기존 파일 내용과 비교하여 변경사항이 있을 때만 저장
            if self.config_path.exists():
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if existing_data == self._config:
                        return  # 변경사항 없음, 저장하지 않음
                except Exception:
                    pass  # 파일 읽기 실패시 저장 진행

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            print(f"✅ 설정 파일 저장됨: {self.config_path}")
        except Exception as e:
            print(f"❌ 설정 파일 저장 실패: {e}")

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """설정 값 조회

        Args:
            section: 섹션 이름 (예: 'news_collection')
            key: 키 이름 (None이면 섹션 전체 반환)
            default: 기본값

        Returns:
            설정 값 또는 기본값
        """
        section_data = self._config.get(section, self.DEFAULT_CONFIG.get(section, {}))

        if key is None:
            return section_data

        # 섹션 데이터에서 키 조회, 없으면 기본 설정에서 조회
        if key in section_data:
            return section_data[key]

        default_section = self.DEFAULT_CONFIG.get(section, {})
        return default_section.get(key, default)

    def set(self, section: str, key: str, value: Any, save: bool = True):
        """설정 값 저장

        Args:
            section: 섹션 이름
            key: 키 이름
            value: 저장할 값
            save: 파일에 즉시 저장할지 여부
        """
        if section not in self._config:
            self._config[section] = {}

        self._config[section][key] = value

        if save:
            self._save()

    def set_section(self, section: str, data: Dict[str, Any], save: bool = True):
        """섹션 전체 저장

        Args:
            section: 섹션 이름
            data: 저장할 데이터 딕셔너리
            save: 파일에 즉시 저장할지 여부
        """
        self._config[section] = data

        if save:
            self._save()

    def get_all(self) -> Dict[str, Any]:
        """전체 설정 반환"""
        return self._config.copy()

    def reset_to_default(self, section: Optional[str] = None, save: bool = True):
        """기본값으로 초기화

        Args:
            section: 초기화할 섹션 (None이면 전체 초기화)
            save: 파일에 즉시 저장할지 여부
        """
        if section is None:
            self._config = self.DEFAULT_CONFIG.copy()
        else:
            if section in self.DEFAULT_CONFIG:
                self._config[section] = self.DEFAULT_CONFIG[section].copy()

        if save:
            self._save()

    def reload(self):
        """설정 파일 다시 로드"""
        self._load()

    # 편의 메서드들
    def get_news_config(self) -> Dict[str, Any]:
        """뉴스 수집 설정 반환 (복사본 반환)"""
        import copy
        config = copy.deepcopy(self.get("news_collection"))
        config['sheet_url'] = self.get("google_sheet", "url")
        config['naver_client_id'] = self.get("naver_api", "client_id")
        config['naver_client_secret'] = self.get("naver_api", "client_secret")
        config['category_keywords'] = copy.deepcopy(self.get("category_keywords") or {})
        return config

    def get_upload_config(self) -> Dict[str, Any]:
        """업로드 감시 설정 반환 (복사본 반환)"""
        import copy
        config = copy.deepcopy(self.get("upload_monitor"))
        config['sheet_url'] = self.get("google_sheet", "url")
        config['site_id'] = self.get("newstown", "site_id")
        config['site_pw'] = self.get("newstown", "site_pw")
        return config

    def get_deletion_config(self) -> Dict[str, Any]:
        """행 삭제 설정 반환 (복사본 반환)"""
        import copy
        config = copy.deepcopy(self.get("row_deletion"))
        config['sheet_url'] = self.get("google_sheet", "url")
        config['completed_column'] = self.get("upload_monitor", "completed_column")
        return config


# 전역 설정 관리자 인스턴스
_global_config: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """전역 설정 관리자 인스턴스 반환"""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config
