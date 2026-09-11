"""설정과 키워드 (SRS 5.1 Setting / Keyword)."""

from sqlalchemy import Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import DEFAULT_USER_ID
from app.db import MYSQL_TABLE_ARGS, Base


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    mail_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    mail_to: Mapped[str] = mapped_column(String(255), nullable=False)
    max_per_source: Mapped[int] = mapped_column(Integer, nullable=False)
    # SR-F-802, 805. Asia/Seoul 기준 자동 실행 시각.
    schedule_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8, server_default=text("8")
    )
    schedule_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    user_id: Mapped[str] = mapped_column(
        String(26), nullable=False, default=DEFAULT_USER_ID
    )


class Keyword(Base):
    """설정과 분리된 별도 엔터티. SR-F-103(중복 등록 불가)을 유일 제약으로 표현한다."""

    __tablename__ = "keywords"
    __table_args__ = (
        # SR-D-207
        UniqueConstraint("user_id", "value", name="uq_keywords_user_id_value"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(26), nullable=False, default=DEFAULT_USER_ID
    )
