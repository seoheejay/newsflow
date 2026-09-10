"""피드 소스 요청·응답 스키마 (SRS 5.1, 부록 A.3).

user_id는 요청에도 응답에도 없다. 단일 값으로만 운용되는 내부 컬럼이고(SRS 2.3),
부록 A.3 예시에도 나오지 않는다.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedSourceBase(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        description="표시명. 중복 불가 (SR-F-206)",
    )
    url_template: str = Field(
        min_length=1,
        max_length=1000,
        description=(
            "주소 템플릿. http:// 또는 https:// 로 시작해야 한다 (SR-F-202). "
            "{keyword}가 있으면 수집 시 키워드로 치환되고, 없어도 등록할 수 있다 (SR-F-205)."
        ),
    )
    sort_order: int = Field(default=0, description="정렬 순서 (SR-F-209)")
    is_active: bool = Field(default=True, description="활성 여부 (SR-F-207)")

    @field_validator("name", "url_template", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        # 공백만 들어온 값이 min_length=1에 걸리도록 한다.
        return v.strip() if isinstance(v, str) else v


class FeedSourceCreate(FeedSourceBase):
    pass


class FeedSourceUpdate(FeedSourceBase):
    """PUT은 전체 교체다. 모든 필드를 받는다."""


class FeedSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url_template: str
    sort_order: int
    is_active: bool
