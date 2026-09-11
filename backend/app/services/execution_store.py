"""실행 행의 생성과 진행 중 판정 (SR-F-701, 705).

수동 실행(POST /collect)과 자동 실행(스케줄러)이 같은 함수를 쓴다.
SR-F-803이 "자동 실행은 수동 실행과 동일한 처리 흐름을 사용해야 한다"고
요구하므로, 실행 행을 만드는 자리도 하나여야 한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.constants import DEFAULT_USER_ID
from app.ids import new_ulid
from app.models import Execution
from app.models.execution import (
    ACTIVE_STATUSES,
    STATUS_QUEUED,
    TRIGGER_MANUAL,
    TRIGGER_SCHEDULED,
)


def find_active_id(db: Session, user_id: str = DEFAULT_USER_ID) -> str | None:
    """진행 중(queued/running)인 실행의 식별자. 없으면 None (SR-F-705)."""
    return db.scalar(
        select(Execution.id).where(
            Execution.user_id == user_id,
            Execution.status.in_(ACTIVE_STATUSES),
        )
    )


def create_queued(
    db: Session,
    user_id: str = DEFAULT_USER_ID,
    trigger: str = TRIGGER_MANUAL,
) -> Execution:
    """queued 상태의 실행 행을 만든다 (SR-F-701, 703, 807)."""
    execution = Execution(
        id=new_ulid(),
        status=STATUS_QUEUED,
        started_at=utcnow(),
        collected_count=0,
        new_count=0,
        trigger=trigger,
        user_id=user_id,
    )
    db.add(execution)
    db.commit()
    return execution


def scheduled_ran_since(db: Session, since: datetime, user_id: str = DEFAULT_USER_ID) -> bool:
    """since 이후에 시작된 자동 실행이 있는지 (SR-F-806의 "하루 한 번")."""
    return (
        db.scalar(
            select(Execution.id).where(
                Execution.user_id == user_id,
                Execution.trigger == TRIGGER_SCHEDULED,
                Execution.started_at >= since,
            )
        )
        is not None
    )
