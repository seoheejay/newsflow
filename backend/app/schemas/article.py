"""기사 응답 스키마 (SRS 부록 A.3).

link_hash, summary, user_id는 내부 컬럼이라 내보내지 않는다.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    link: str
    keyword: str
    site: str
    published_at: datetime | None  # SR-F-304로 비어 있을 수 있다
    collected_at: datetime
