"""설정 요청·응답 스키마 (SR-F-101~106, 부록 A.3)."""

from pydantic import BaseModel, EmailStr, Field, field_validator

KEYWORD_MAX_LEN = 64  # SR-F-102
KEYWORD_MAX_COUNT = 20  # SR-F-102
SUBJECT_MAX_LEN = 200  # SR-F-106
MAX_PER_SOURCE_MIN = 1  # SR-F-105
MAX_PER_SOURCE_MAX = 100  # SR-F-105


class SettingsOut(BaseModel):
    """GET /settings. mail_to는 아직 비어 있을 수 있으므로 EmailStr이 아니다."""

    mail_subject: str
    mail_to: str
    max_per_source: int
    keywords: list[str]


class SettingsUpdate(BaseModel):
    mail_subject: str = Field(
        min_length=1, max_length=SUBJECT_MAX_LEN, description="메일 제목 (SR-F-106)"
    )
    # SR-F-104: RFC 5322. 불만족 시 400 VALIDATION_ERROR + fields=["mail_to"]
    mail_to: EmailStr
    max_per_source: int = Field(
        ge=MAX_PER_SOURCE_MIN,
        le=MAX_PER_SOURCE_MAX,
        description="소스당 최대 수집 건수 (SR-F-105)",
    )
    keywords: list[str] = Field(
        max_length=KEYWORD_MAX_COUNT, description="검색 키워드 (SR-F-102)"
    )

    @field_validator("mail_subject", mode="before")
    @classmethod
    def _strip_subject(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("keywords")
    @classmethod
    def _check_keywords(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            value = raw.strip()
            if not value:
                raise ValueError("키워드는 1자 이상이어야 합니다")
            if len(value) > KEYWORD_MAX_LEN:
                raise ValueError(f"키워드는 {KEYWORD_MAX_LEN}자 이하여야 합니다")
            # SR-F-103. 조용히 합치지 않고 거부한다 - 화면이 보낸 목록과
            # 저장 결과가 달라지면 사용자가 무엇이 지워졌는지 알 수 없다.
            if value in cleaned:
                raise ValueError(f"중복된 키워드입니다: {value}")
            cleaned.append(value)
        return cleaned
