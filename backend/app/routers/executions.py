"""수집 실행 요청과 실행 이력 (SR-F-701~707, 부록 A.1)."""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.constants import DEFAULT_USER_ID
from app.db import get_db
from app.errors import ErrorResponse, ExecutionInProgressError, NotFoundError
from app.models import Execution
from app.models.execution import STATUS_FAILED, TRIGGER_MANUAL
from app.schemas.common import ListResponse
from app.schemas.execution import CollectAccepted, ExecutionDetail, ExecutionSummary
from app.services import execution_store
from app.tasks import collect_task

logger = logging.getLogger(__name__)

DEFAULT_ITEMS_PER_PAGE = 20
MAX_ITEMS_PER_PAGE = 100

router = APIRouter(tags=["executions"])


@router.post(
    "/collect",
    response_model=CollectAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"model": ErrorResponse}},
)
def request_collection(db: Session = Depends(get_db)) -> CollectAccepted:
    """SR-F-701. 처리 완료를 기다리지 않고 즉시 응답한다 (SR-N-102, 1초 이내)."""
    # SR-F-705. 진행 중인 실행이 있으면 409.
    if execution_store.find_active_id(db, DEFAULT_USER_ID):
        raise ExecutionInProgressError()

    execution = execution_store.create_queued(
        db, DEFAULT_USER_ID, trigger=TRIGGER_MANUAL
    )

    try:
        collect_task.delay(execution.id)
    except Exception:
        # 부록 B.2: 큐 등록 후 처리기가 시작하지 못하면 queued -> failed.
        # 브로커가 죽어 있어도 실행 행은 사유를 남기고 끝나야 한다.
        logger.exception("작업 큐 등록 실패: execution %s", execution.id)
        execution.status = STATUS_FAILED
        execution.error = "작업 큐에 등록하지 못했습니다. Redis 상태를 확인하세요"
        execution.finished_at = utcnow()
        db.commit()
        raise

    return CollectAccepted(execution_id=execution.id, status=execution.status)


@router.get("/executions", response_model=ListResponse[ExecutionSummary])
def list_executions(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(
        default=DEFAULT_ITEMS_PER_PAGE, ge=1, le=MAX_ITEMS_PER_PAGE
    ),
) -> ListResponse[ExecutionSummary]:
    """SR-F-707. 시작 시각 내림차순."""
    total_count = (
        db.scalar(
            select(func.count())
            .select_from(Execution)
            .where(Execution.user_id == DEFAULT_USER_ID)
        )
        or 0
    )
    rows = db.scalars(
        select(Execution)
        .where(Execution.user_id == DEFAULT_USER_ID)
        .order_by(Execution.started_at.desc(), Execution.id.desc())
        .offset((page - 1) * items_per_page)
        .limit(items_per_page)
    ).all()
    return ListResponse[ExecutionSummary](
        total_count=total_count,
        page=page,
        items_per_page=items_per_page,
        items=[ExecutionSummary.model_validate(row) for row in rows],
    )


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionDetail,
    responses={404: {"model": ErrorResponse}},
)
def get_execution(execution_id: str, db: Session = Depends(get_db)) -> Execution:
    """SR-F-706. 실행 식별자로 상태를 조회한다."""
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise NotFoundError("실행을 찾을 수 없습니다")
    return execution
