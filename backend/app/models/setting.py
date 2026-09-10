"""설정과 키워드 (SRS 5.1 Setting / Keyword).

이번 슬라이스에서는 스키마만 정의한다. SR-F-1xx 구현은 이후 작업.
"""

from sqlalchemy import Integer, String, UniqueConstraint
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
