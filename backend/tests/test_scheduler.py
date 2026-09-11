"""자동 실행 (SR-F-801~804)."""

import contextlib
from datetime import datetime

import httpx
import pytest
from celery.schedules import crontab
from sqlalchemy.orm import Session

from app.clock import KST
from app.constants import DEFAULT_USER_ID
from app.models import Article, Execution, Setting
from app.models.execution import (
    ACTIVE_STATUSES,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    TRIGGER_MANUAL,
    TRIGGER_SCHEDULED,
)
from app.services import execution_store
from app.tasks import should_run_now
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


def _tick(db_session: Session, monkeypatch, **kwargs):
    """분 단위 틱. 지금이 실행 시각인지 판단하는 경로까지 태운다."""
    import app.tasks as tasks

    @contextlib.contextmanager
    def fake_session():
        yield db_session

    monkeypatch.setattr(tasks, "SessionLocal", fake_session)
    return tasks.tick_scheduled_collection(**kwargs)


# ----------------------------------------------------------------- 801, 802


def test_SR_F_801_beat_ticks_every_minute() -> None:
    entry = celery_app.conf.beat_schedule["schedule-tick"]

    assert entry["task"] == "app.tasks.scheduled_collect"
    # SR-F-805로 시각이 바뀔 수 있으므로 crontab에 시각을 굳히지 않는다.
    assert isinstance(entry["schedule"], crontab)
    assert entry["schedule"].hour == set(range(24))


def test_SR_F_802_default_is_eight_in_the_morning() -> None:
    from app.services.settings_store import (
        DEFAULT_SCHEDULE_HOUR,
        DEFAULT_SCHEDULE_MINUTE,
    )

    assert (DEFAULT_SCHEDULE_HOUR, DEFAULT_SCHEDULE_MINUTE) == (8, 0)


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


# --------------------------------------------------- 805, 806, 807 (틱 판정)


def _kst(h: int, m: int, day: int = 11) -> datetime:
    return datetime(2026, 9, day, h, m, tzinfo=KST)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_kst(8, 0), True),  # 정각
        (_kst(8, 4), True),  # 지연 허용 구간 안
        (_kst(8, 5), False),  # 구간 밖
        (_kst(7, 59), False),  # 아직 이름
        (_kst(20, 0), False),
    ],
)
def test_SR_F_806_fire_window_is_the_scheduled_minute_plus_tolerance(
    now: datetime, expected: bool
) -> None:
    within, scheduled = should_run_now(now, 8, 0)

    assert within is expected
    assert scheduled.hour == 8 and scheduled.minute == 0


def test_SR_F_805_tick_uses_the_time_saved_in_settings(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    row = db_session.query(Setting).one()
    row.schedule_hour, row.schedule_minute = 21, 30
    db_session.commit()

    # 저장한 시각이 아니면 돌지 않는다
    assert (
        _tick(db_session, monkeypatch, now_kst=_kst(8, 0), client=_rss_client()) is None
    )
    # 저장한 시각이면 돈다
    status = _tick(
        db_session,
        monkeypatch,
        now_kst=_kst(21, 30),
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )
    assert status == STATUS_SUCCESS


def test_SR_F_806_does_not_run_twice_in_the_same_window(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    first = _tick(
        db_session,
        monkeypatch,
        now_kst=_kst(8, 0),
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )
    second = _tick(
        db_session,
        monkeypatch,
        now_kst=_kst(8, 1),
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )

    assert first == STATUS_SUCCESS
    assert second is None  # 그 날 몫은 이미 돌았다
    assert db_session.query(Execution).count() == 1


def test_SR_F_806_runs_again_the_next_day(db_session: Session, monkeypatch) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    _tick(db_session, monkeypatch, now_kst=_kst(8, 0, day=11),
          client=_rss_client(), mail_sender=lambda **kw: None)
    second = _tick(db_session, monkeypatch, now_kst=_kst(8, 0, day=12),
                   client=_rss_client(), mail_sender=lambda **kw: None)

    assert second == STATUS_SUCCESS
    assert db_session.query(Execution).count() == 2


def test_SR_F_806_manual_run_does_not_suppress_the_scheduled_one(
    db_session: Session, monkeypatch
) -> None:
    """수동으로 한 번 돌렸다고 그 날 자동 실행을 건너뛰면 안 된다."""
    _seed(db_session)
    _seed_setting(db_session)
    manual = execution_store.create_queued(db_session, DEFAULT_USER_ID, trigger=TRIGGER_MANUAL)
    manual.status = STATUS_SUCCESS
    db_session.commit()

    status = _tick(
        db_session,
        monkeypatch,
        now_kst=_kst(8, 0),
        client=_rss_client(),
        mail_sender=lambda **kw: None,
    )

    assert status == STATUS_SUCCESS
    assert db_session.query(Execution).count() == 2


def test_SR_F_807_scheduled_run_is_marked_scheduled(
    db_session: Session, monkeypatch
) -> None:
    _seed(db_session)
    _seed_setting(db_session)

    _run_scheduled(
        db_session, monkeypatch, client=_rss_client(), mail_sender=lambda **kw: None
    )

    assert db_session.query(Execution).one().trigger == TRIGGER_SCHEDULED


def test_SR_F_807_manual_run_is_marked_manual(db_session: Session) -> None:
    row = execution_store.create_queued(db_session, DEFAULT_USER_ID)
    assert row.trigger == TRIGGER_MANUAL
