# -*- coding: utf-8 -*-
"""
Configuration Schema Definitions with Pydantic v2 Validation

@TASK T7 - Pydantic 검증 추가
@SPEC CLAUDE.md#Configuration
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator


class CategoryKeywords(BaseModel):
    """카테고리별 키워드 설정"""
    core: List[str] = Field(default_factory=list, description="핵심 키워드 목록")
    general: List[str] = Field(default_factory=list, description="일반 키워드 목록")

    @field_validator("core", "general")
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        """키워드 유효성 검사"""
        if not isinstance(v, list):
            raise ValueError("키워드는 리스트 형식이어야 합니다.")
        for keyword in v:
            if not isinstance(keyword, str):
                raise ValueError(f"키워드는 문자열이어야 합니다: {keyword}")
            if not keyword.strip():
                raise ValueError("빈 키워드는 허용되지 않습니다.")
        return v


class NewsCollectionConfig(BaseModel):
    """뉴스 수집 설정"""
    keywords: Dict[str, int] = Field(
        default={"연애": 15, "경제": 15, "스포츠": 15},
        description="카테고리별 수집 개수"
    )
    display_count: int = Field(default=30, ge=1, le=100, description="표시할 뉴스 개수")
    max_workers: int = Field(default=10, ge=1, le=50, description="최대 워커 수")
    sort: str = Field(default="date", pattern="^(date|relevance)$", description="정렬 방식")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: Dict[str, int]) -> Dict[str, int]:
        """키워드 설정 유효성 검사"""
        if not v:
            raise ValueError("키워드 설정은 비어있을 수 없습니다.")
        for category, count in v.items():
            if not isinstance(category, str):
                raise ValueError(f"카테고리는 문자열이어야 합니다: {category}")
            if not isinstance(count, int) or count < 1 or count > 100:
                raise ValueError(f"수집 개수는 1~100 사이 정수여야 합니다: {category}={count}")
        return v


class UploadMonitorConfig(BaseModel):
    """업로드 감시 설정"""
    check_interval: int = Field(default=30, ge=10, le=3600, description="체크 간격(초)")
    completed_column: int = Field(default=8, ge=1, le=26, description="완료 표시 열 번호")
    concurrent_uploads: int = Field(default=1, ge=1, le=10, description="동시 업로드 수")


class RowDeletionConfig(BaseModel):
    """행 삭제 설정"""
    delete_interval: int = Field(default=60, ge=30, le=3600, description="삭제 간격(초)")
    max_delete_count: int = Field(default=10, ge=1, le=100, description="최대 삭제 개수")


class GoogleSheetConfig(BaseModel):
    """Google Sheets 설정"""
    url: str = Field(default="", description="Google Sheets URL")


class NaverApiConfig(BaseModel):
    """Naver API 설정"""
    client_id: str = Field(default="", description="Naver API Client ID")
    client_secret: str = Field(default="", description="Naver API Client Secret")


class NewsScheduleConfig(BaseModel):
    """뉴스 스케줄 설정"""
    enabled: bool = Field(default=False, description="스케줄 활성화 여부")
    interval_hours: int = Field(default=3, ge=1, le=24, description="스케줄 간격(시간)")
    last_run: Optional[str] = Field(default=None, description="마지막 실행 시간")


class PlatformCredentials(BaseModel):
    """플랫폼 인증 정보"""
    site_id: str = Field(default="", description="사이트 ID")
    site_pw: str = Field(default="", description="사이트 비밀번호")


class PlatformConfig(BaseModel):
    """업로드 플랫폼 설정"""
    enabled: bool = Field(default=False, description="활성화 여부")
    display_name: str = Field(default="", description="표시 이름")
    title_column: int = Field(default=5, ge=1, le=26, description="제목 열 번호")
    content_column: int = Field(default=6, ge=1, le=26, description="내용 열 번호")
    completed_column: int = Field(default=8, ge=1, le=26, description="완료 열 번호")
    credentials_section: str = Field(default="", description="인증 정보 섹션")


class UploadPlatformsConfig(BaseModel):
    """업로드 플랫폼들 설정"""
    golftimes: PlatformConfig = Field(
        default=PlatformConfig(
            enabled=False,
            display_name="골프타임즈",
            title_column=10,
            content_column=11,
            completed_column=12,
            credentials_section="golftimes"
        )
    )


class CategoryKeywordsConfig(BaseModel):
    """전체 카테고리 키워드 설정"""
    연애: CategoryKeywords = Field(
        default=CategoryKeywords(
            core=["연애", "열애", "커플", "결혼", "고백"],
            general=["신랑", "신부", "웨딩", "혼수"]
        )
    )
    경제: CategoryKeywords = Field(
        default=CategoryKeywords(
            core=["경제", "증시", "코스피", "코스닥", "나스닥"],
            general=["은행", "금융", "증권"]
        )
    )
    스포츠: CategoryKeywords = Field(
        default=CategoryKeywords(
            core=["스포츠", "야구", "축구", "농구", "배구"],
            general=["선수", "감독", "코치"]
        )
    )


class AppConfig(BaseModel):
    """전체 애플리케이션 설정"""
    news_collection: NewsCollectionConfig = Field(default_factory=NewsCollectionConfig)
    category_keywords: CategoryKeywordsConfig = Field(default_factory=CategoryKeywordsConfig)
    upload_monitor: UploadMonitorConfig = Field(default_factory=UploadMonitorConfig)
    row_deletion: RowDeletionConfig = Field(default_factory=RowDeletionConfig)
    google_sheet: GoogleSheetConfig = Field(default_factory=GoogleSheetConfig)
    naver_api: NaverApiConfig = Field(default_factory=NaverApiConfig)
    news_schedule: NewsScheduleConfig = Field(default_factory=NewsScheduleConfig)
    # @SECURITY A05 - 하드코딩된 비밀번호 제거
    golftimes: PlatformCredentials = Field(
        default=PlatformCredentials(site_id="thegolftimes", site_pw="")
    )
    upload_platforms: Dict[str, PlatformConfig] = Field(
        default_factory=lambda: {
            "golftimes": PlatformConfig(
                enabled=False,
                display_name="골프타임즈",
                title_column=10,
                content_column=11,
                completed_column=12,
                credentials_section="golftimes"
            )
        }
    )

    class Config:
        """Pydantic 설정"""
        validate_assignment = True
        extra = "allow"  # 추가 필드 허용 (확장성)
        arbitrary_types_allowed = True

    @model_validator(mode="before")
    @classmethod
    def validate_before(cls, data: Any) -> Any:
        """모델 생성 전 검사"""
        return data


def validate_config_dict(config_dict: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[AppConfig]]:
    """
    설정 딕셔너리를 Pydantic으로 검증

    Args:
        config_dict: 검증할 설정 딕셔너리

    Returns:
        (검증성공, 에러메시지, 검증된모델)
    """
    try:
        validated = AppConfig(**config_dict)
        return True, None, validated
    except Exception as e:
        error_msg = str(e)
        # Pydantic 에러를 한글로 변환
        if "validation error" in error_msg:
            error_msg = f"설정 값 검증 실패: {error_msg}"
        return False, error_msg, None


def validate_section(section_name: str, section_data: Any) -> Tuple[bool, Optional[str], Any]:
    """
    특정 섹션만 검증

    Args:
        section_name: 섹션 이름
        section_data: 섹션 데이터

    Returns:
        (검증성공, 에러메시지, 검증된모델)
    """
    section_models = {
        "news_collection": NewsCollectionConfig,
        "category_keywords": CategoryKeywordsConfig,
        "upload_monitor": UploadMonitorConfig,
        "row_deletion": RowDeletionConfig,
        "google_sheet": GoogleSheetConfig,
        "naver_api": NaverApiConfig,
        "news_schedule": NewsScheduleConfig,
        "golftimes": PlatformCredentials,
    }

    model_class = section_models.get(section_name)
    if not model_class:
        # 알 수 없는 섹션은 통과 (확장성)
        return True, None, section_data

    try:
        if isinstance(section_data, dict):
            validated = model_class(**section_data)
            return True, None, validated
        else:
            return False, f"섹션 데이터가 딕셔너리 형식이어야 합니다: {section_name}", None
    except Exception as e:
        error_msg = f"섹션 '{section_name}' 검증 실패: {str(e)}"
        return False, error_msg, None
