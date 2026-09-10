"""피드 소스 (SRS 5.1 FeedSource)."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import DEFAULT_USER_ID
from app.db import MYSQL_TABLE_ARGS, Base


class FeedSource(Base):
    __tablename__ = "feed_sources"
    __table_args__ = (
        # SR-F-206 / SR-D-202: 표시명 중복 불가. 라우터가 이 이름으로 409를 판정한다.
        UniqueConstraint("name", name="uq_feed_sources_name"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 인덱스를 걸지 않는다. utf8mb4에서 1000자는 4000바이트로 InnoDB 키 길이 한도를 넘는다.
    url_template: Mapped[str] = mapped_column(String(1000), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    user_id: Mapped[str] = mapped_column(
        String(26), nullable=False, default=DEFAULT_USER_ID
    )
