"""Celery 작업 (SRS 부록 B.1의 4~17단계).

수집 로직 자체는 app.services.pipeline에 있다. 여기서는 실행 상태를
기록하는 일만 한다 (SR-F-702, 703, 704).
"""

from __future__ import annotations

import logging

from app.clock import utcnow
from app.constants import DEFAULT_USER_ID
from app.db import SessionLocal
from app.models import Execution
from app.models.execution import STATUS_FAILED, STATUS_RUNNING, STATUS_SUCCESS
from app.services.pipeline import run_collection
from app.worker import celery_app

logger = logging.getLogger(__name__)


def run_collection_execution(
    execution_id: str, *, user_id: str = DEFAULT_USER_ID, **kwargs
) -> str:
    """실행 하나를 끝까지 수행하고 최종 상태를 돌려준다.

    Celery 밖에서도 부를 수 있게 순수 함수로 둔다 (SR-N-402, 테스트).
    """
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if execution is None:
            logger.error("execution %s 없음", execution_id)
            return STATUS_FAILED

        # 4단계: 작업을 가져갔으니 running으로 바꾼다.
        execution.status = STATUS_RUNNING
        db.commit()

        try:
            result = run_collection(db, store=True, send=True, user_id=user_id, **kwargs)
        except Exception as exc:  # noqa: BLE001 - SR-N-204: 예외가 나도 시스템은 산다
            logger.exception("execution %s 실패", execution_id)
            execution.status = STATUS_FAILED
            execution.error = f"{type(exc).__name__}: {exc}"[:1000]
            execution.finished_at = utcnow()
            db.commit()
            return STATUS_FAILED

        # 17단계: 집계 기록 (SR-F-703, 704)
        execution.collected_count = result.collected_count
        execution.new_count = result.new_count
        execution.node_logs = [log.to_dict() for log in result.node_logs]
        execution.error = result.error
        execution.status = STATUS_FAILED if result.failed else STATUS_SUCCESS
        execution.finished_at = utcnow()
        db.commit()
        return execution.status


@celery_app.task(name="app.tasks.collect")
def collect_task(execution_id: str) -> str:
    return run_collection_execution(execution_id)
