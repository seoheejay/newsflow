"""실행 요청·상태·이력 (SR-F-701~707, 부록 A.3, B.2)."""

from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.models import Article, Execution
from app.models.execution import (
    ACTIVE_STATUSES,
    FINAL_STATUSES,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
)
from tests.test_pipeline import RSS, _seed, _seed_setting


@pytest.fixture
def no_queue(monkeypatch):
    """POST /collect가 Redis에 붙지 않게 한다. 등록된 execution_id를 모은다."""
    sent: list[str] = []
    monkeypatch.setattr(
        "app.routers.executions.collect_task",
        type("T", (), {"delay": staticmethod(lambda eid: sent.append(eid))})(),
    )
    return sent


def _execution(db: Session, **overrides) -> Execution:
    values = {
        "id": "01EEEEEEEEEEEEEEEEEEEEEEEE",
        "status": STATUS_SUCCESS,
        "started_at": datetime(2026, 9, 10, 0, 0),
        "finished_at": datetime(2026, 9, 10, 0, 1),
        "collected_count": 5,
        "new_count": 2,
        "error": None,
        "user_id": DEFAULT_USER_ID,
    }
    values.update(overrides)
    row = Execution(**values)
    db.add(row)
    db.commit()
    return row


# ----------------------------------------------------------------- 701, 705


def test_SR_F_701_collect_returns_202_with_execution_id(
    client: TestClient, no_queue
) -> None:
    res = client.post("/collect")

    assert res.status_code == 202
    body = res.json()
    assert len(body["execution_id"]) == 26
    assert body["status"] == STATUS_QUEUED


def test_SR_F_701_collect_records_a_queued_execution(
    client: TestClient, db_session: Session, no_queue
) -> None:
    execution_id = client.post("/collect").json()["execution_id"]

    row = db_session.get(Execution, execution_id)
    assert row.status == STATUS_QUEUED
    assert row.started_at is not None
    assert row.finished_at is None


def test_SR_F_701_collect_enqueues_the_task(client: TestClient, no_queue) -> None:
    execution_id = client.post("/collect").json()["execution_id"]
    assert no_queue == [execution_id]


@pytest.mark.parametrize("active", sorted(ACTIVE_STATUSES))
def test_SR_F_705_second_request_while_active_returns_409(
    client: TestClient, db_session: Session, no_queue, active: str
) -> None:
    _execution(db_session, status=active, finished_at=None)

    res = client.post("/collect")

    assert res.status_code == 409
    assert res.json()["code"] == "EXECUTION_IN_PROGRESS"
    assert no_queue == []  # 큐에 넣지 않는다


@pytest.mark.parametrize("final", sorted(FINAL_STATUSES))
def test_SR_F_705_finished_execution_does_not_block_a_new_one(
    client: TestClient, db_session: Session, no_queue, final: str
) -> None:
    _execution(db_session, status=final)

    assert client.post("/collect").status_code == 202


def test_SR_F_705_queue_failure_marks_execution_failed(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    def boom(execution_id):
        raise OSError("redis 없음")

    monkeypatch.setattr(
        "app.routers.executions.collect_task",
        type("T", (), {"delay": staticmethod(boom)})(),
    )

    # client 픽스처가 get_db 오버라이드를 걸어둔 상태에서, 서버 예외를 다시
    # 던지지 않는 클라이언트로 실제 500 응답을 확인한다.
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as raw:
        res = raw.post("/collect")
    assert res.status_code == 500
    assert res.json()["code"] == "INTERNAL_ERROR"

    # 부록 B.2: queued -> failed. 사유가 남아야 다음 요청이 409에 막히지 않는다.
    row = db_session.query(Execution).one()
    assert row.status == STATUS_FAILED
    assert "Redis" in row.error
    assert row.finished_at is not None


# ---------------------------------------------------------------------- 706


def test_SR_F_706_get_execution_returns_appendix_a3_shape(
    client: TestClient, db_session: Session
) -> None:
    _execution(
        db_session,
        node_logs=[{"site": "구글", "keyword": "AI", "count": 10, "elapsed_ms": 812}],
    )

    body = client.get("/executions/01EEEEEEEEEEEEEEEEEEEEEEEE").json()

    assert set(body) == {
        "id",
        "status",
        "started_at",
        "finished_at",
        "collected_count",
        "new_count",
        "error",
        "node_logs",
    }
    assert body["node_logs"][0]["site"] == "구글"


def test_SR_F_706_unknown_execution_returns_404(client: TestClient) -> None:
    res = client.get("/executions/NOPE")

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------- 707


def test_SR_F_707_history_is_ordered_by_started_at_desc(
    client: TestClient, db_session: Session
) -> None:
    _execution(db_session, id="01A" + "0" * 23, started_at=datetime(2026, 9, 8, 0, 0))
    _execution(db_session, id="01B" + "0" * 23, started_at=datetime(2026, 9, 10, 0, 0))
    _execution(db_session, id="01C" + "0" * 23, started_at=datetime(2026, 9, 9, 0, 0))

    items = client.get("/executions").json()["items"]

    assert [i["id"][:3] for i in items] == ["01B", "01C", "01A"]


def test_SR_I_304_history_uses_the_envelope(
    client: TestClient, db_session: Session
) -> None:
    _execution(db_session)

    body = client.get("/executions").json()
    assert set(body) == {"total_count", "page", "items_per_page", "items"}
    assert body["total_count"] == 1
    # 목록에는 node_logs를 싣지 않는다
    assert "node_logs" not in body["items"][0]


def test_SR_F_707_empty_history_returns_empty_envelope(client: TestClient) -> None:
    body = client.get("/executions").json()
    assert body["total_count"] == 0
    assert body["items"] == []


# --------------------------------------------------- 작업 본체 (부록 B.1 4~17)


def _run_task(db_session: Session, execution_id: str, monkeypatch, **kwargs):
    """run_collection_execution이 테스트 세션을 쓰도록 SessionLocal을 갈아끼운다."""
    import contextlib

    import app.tasks as tasks

    @contextlib.contextmanager
    def fake_session():
        yield db_session

    monkeypatch.setattr(tasks, "SessionLocal", fake_session)
    return tasks.run_collection_execution(execution_id, **kwargs)


def _rss_client() -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, content=RSS.encode())
        )
    )


def test_SR_F_703_task_records_counts_and_finish_time(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None, collected_count=0, new_count=0)

    status = _run_task(
        db_session,
        "01EEEEEEEEEEEEEEEEEEEEEEEE",
        monkeypatch,
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )

    row = db_session.get(Execution, "01EEEEEEEEEEEEEEEEEEEEEEEE")
    assert status == STATUS_SUCCESS
    assert row.status == STATUS_SUCCESS
    assert row.collected_count == 2
    assert row.new_count == 2
    assert row.finished_at is not None
    assert row.error is None


def test_SR_F_704_task_records_node_logs(db_session: Session, monkeypatch) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None)

    _run_task(
        db_session,
        "01EEEEEEEEEEEEEEEEEEEEEEEE",
        monkeypatch,
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )

    logs = db_session.get(Execution, "01EEEEEEEEEEEEEEEEEEEEEEEE").node_logs
    assert logs and logs[0]["site"] == "구글"
    assert "elapsed_ms" in logs[0]


def test_SR_F_601_task_stores_articles(db_session: Session, monkeypatch) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None)

    _run_task(
        db_session,
        "01EEEEEEEEEEEEEEEEEEEEEEEE",
        monkeypatch,
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )

    assert db_session.query(Article).count() == 2


def test_SR_F_310_task_marks_failed_when_every_target_fails(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None)

    status = _run_task(
        db_session,
        "01EEEEEEEEEEEEEEEEEEEEEEEE",
        monkeypatch,
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
    )

    row = db_session.get(Execution, "01EEEEEEEEEEEEEEEEEEEEEEEE")
    assert status == STATUS_FAILED
    assert row.status == STATUS_FAILED
    assert row.error == "전체 주소 수집 실패"
    assert row.finished_at is not None


def test_SR_N_204_unexpected_exception_is_recorded_not_raised(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None)

    def explode(*args, **kwargs):
        raise RuntimeError("예상 못한 오류")

    monkeypatch.setattr("app.tasks.run_collection", explode)

    status = _run_task(db_session, "01EEEEEEEEEEEEEEEEEEEEEEEE", monkeypatch)

    row = db_session.get(Execution, "01EEEEEEEEEEEEEEEEEEEEEEEE")
    assert status == STATUS_FAILED
    assert "RuntimeError" in row.error
    assert row.finished_at is not None


def test_SR_F_702_task_sets_running_before_work(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    _execution(db_session, status=STATUS_QUEUED, finished_at=None)
    seen: list[str] = []

    def capture(db, **kwargs):
        seen.append(db.get(Execution, "01EEEEEEEEEEEEEEEEEEEEEEEE").status)
        raise RuntimeError("중단")

    monkeypatch.setattr("app.tasks.run_collection", capture)
    _run_task(db_session, "01EEEEEEEEEEEEEEEEEEEEEEEE", monkeypatch)

    assert seen == [STATUS_RUNNING]


def test_task_on_missing_execution_returns_failed(
    db_session: Session, monkeypatch
) -> None:
    assert _run_task(db_session, "NOPE", monkeypatch) == STATUS_FAILED
