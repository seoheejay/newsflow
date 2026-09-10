"""실행 이력 (SRS 5.1 Execution).

이번 슬라이스에서는 스키마만 정의한다. SR-F-7xx 구현은 이후 작업.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import DEFAULT_USER_ID
from app.db import MYSQL_TABLE_ARGS, Base


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    # SR-F-702: queued / running / success / failed
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SR-F-704: 피드 소스별 수집 결과와 소요 시간.
    node_logs: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(26), nullable=False, default=DEFAULT_USER_ID
    )
