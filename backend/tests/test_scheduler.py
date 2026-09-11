"""자동 실행 (SR-F-801~804)."""

import contextlib

import httpx
from celery.schedules import crontab
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Article, Execution
from app.models.execution import (
    ACTIVE_STATUSES,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
)
from app.worker import celery_app
from tests.test_pipeline import RSS, _seed, _seed_setting


def _rss_client() -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, content=RSS.encode())
        )
    )


def _run_scheduled(db_session: Session, monkeypatch, **kwargs):
    """자동 실행이 테스트 세션을 쓰도록 SessionLocal을 갈아끼운다."""
    import app.tasks as tasks

    @contextlib.contextmanager
    def fake_session():
        yield db_session

    monkeypatch.setattr(tasks, "SessionLocal", fake_session)
    return tasks.start_scheduled_collection(**kwargs)


# ----------------------------------------------------------------- 801, 802


def test_SR_F_801_beat_schedule_is_registered() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "daily-collect" in schedule
    assert schedule["daily-collect"]["task"] == "app.tasks.scheduled_collect"


def test_SR_F_802_schedule_uses_configured_hour_and_minute() -> None:
    entry = celery_app.conf.beat_schedule["daily-collect"]["schedule"]

    assert isinstance(entry, crontab)
    assert entry.hour == {settings.schedule_hour}
    assert entry.minute == {settings.schedule_minute}


def test_SR_F_802_default_is_eight_in_the_morning() -> None:
    # .env가 값을 덮을 수 있으므로 기본값 자체를 확인한다.
    from app.config import Settings

    defaults = Settings(database_url="sqlite+pysqlite:///:memory:")
    assert defaults.schedule_hour == 8
    assert defaults.schedule_minute == 0


def test_SR_F_802_crontab_is_interpreted_in_seoul_time() -> None:
    # SR-F-802가 "Asia/Seoul 08:00"이라 했으므로 crontab도 그 시간대여야 한다.
    assert str(celery_app.conf.timezone) == "Asia/Seoul"


def test_SR_F_801_scheduled_task_is_registered_on_the_app() -> None:
    assert "app.tasks.scheduled_collect" in celery_app.tasks


# ----------------------------------------------------------------- 803, 804


def test_SR_F_803_scheduled_run_uses_the_same_flow(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    status = _run_scheduled(
        db_session, monkeypatch, client=_rss_client(), mail_sender=lambda **kw: None
    )

    assert status == STATUS_SUCCESS
    # 수동 실행과 같은 결과: 기사가 저장되고 메일 경로를 탄다
    assert db_session.query(Article).count() == 2


def test_SR_F_804_scheduled_run_is_recorded_in_history(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    _run_scheduled(
        db_session, monkeypatch, client=_rss_client(), mail_sender=lambda **kw: None
    )

    row = db_session.query(Execution).one()
    assert row.status == STATUS_SUCCESS
    assert row.collected_count == 2
    assert row.new_count == 2
    assert row.started_at is not None
    assert row.finished_at is not None
    assert row.node_logs  # SR-F-704


def test_SR_F_804_scheduled_failure_is_recorded_too(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    status = _run_scheduled(
        db_session,
        monkeypatch,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        ),
    )

    row = db_session.query(Execution).one()
    assert status == STATUS_FAILED
    assert row.status == STATUS_FAILED
    assert row.error == "전체 주소 수집 실패"


# --------------------------------------------------------- 진행 중일 때


def test_SR_F_705_scheduled_run_skips_when_one_is_active(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    db_session.add(
        Execution(
            id="01RUNNING00000000000000000",
            status=STATUS_RUNNING,
            started_at=__import__("datetime").datetime(2026, 9, 11, 0, 0),
            collected_count=0,
            new_count=0,
            user_id="00000000000000000000000000",
        )
    )
    db_session.commit()

    status = _run_scheduled(db_session, monkeypatch, client=_rss_client())

    # 스케줄러에는 409를 알려줄 상대가 없다. 조용히 건너뛰고 행을 늘리지 않는다.
    assert status is None
    assert db_session.query(Execution).count() == 1
    assert db_session.query(Article).count() == 0


def test_SR_F_705_active_statuses_cover_queued_and_running() -> None:
    assert ACTIVE_STATUSES == {"queued", "running"}
