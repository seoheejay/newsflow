"""기사 (SRS 5.1 Article).

이번 슬라이스에서는 스키마만 정의한다. SR-F-6xx 구현은 이후 작업.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import DEFAULT_USER_ID
from app.db import MYSQL_TABLE_ARGS, Base


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        # SR-D-201: 중복 제거(SR-F-405)의 뿌리.
        UniqueConstraint("link_hash", name="uq_articles_link_hash"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    link_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    # 피드 소스 표시명의 스냅샷. FK가 아니므로 피드 소스를 삭제해도 기사는 남는다 (SR-F-208).
    site: Mapped[str] = mapped_column(String(64), nullable=False)
    # SR-F-304: 발행일시를 알 수 없는 기사도 누락 없이 보관한다.
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # UR-DAT-06: 이번 릴리스 미사용. 이후 요약 기능 추가 시 마이그레이션을 피하기 위한 사전 조치.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(26), nullable=False, default=DEFAULT_USER_ID
    )
