"""실행 응답 스키마 (SRS 부록 A.3)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CollectAccepted(BaseModel):
    """POST /collect 의 202 응답."""

    execution_id: str
    status: str


class ExecutionSummary(BaseModel):
    """실행 이력 목록의 항목. node_logs는 크므로 뺀다."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    collected_count: int
    new_count: int
    error: str | None
    trigger: str


class ExecutionDetail(ExecutionSummary):
    """GET /executions/{id}. 부록 A.3의 형태."""

    node_logs: list[dict[str, Any]] | None = None
