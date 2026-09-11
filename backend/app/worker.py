"""Celery 애플리케이션 (SRS 2.1의 작업 처리기).

Windows에서 워커를 띄울 때는 --pool=solo가 필요하다. 기본 prefork 풀은
fork()에 기대는데 Windows에는 fork가 없다.

    poetry run celery -A app.worker.celery_app worker --loglevel=info --pool=solo
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "newsflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # SR-F-802가 "Asia/Seoul 08:00"을 기본값으로 못박았으므로 crontab도 그
    # 시간대로 해석해야 한다. enable_utc=True라 메시지의 시각은 UTC로 나가고,
    # DB 보관 시각은 app.clock.utcnow()가 따로 만들므로 SR-D-203과 무관하다.
    timezone="Asia/Seoul",
    enable_utc=True,
    # 작업을 하나씩만 가져간다. 수집은 동시 실행을 막고 있으므로(SR-F-705)
    # 미리 쌓아둘 이유가 없다.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# SR-F-801, 802. 매일 지정된 시각에 자동 실행한다.
celery_app.conf.beat_schedule = {
    "daily-collect": {
        "task": "app.tasks.scheduled_collect",
        "schedule": crontab(
            hour=settings.schedule_hour, minute=settings.schedule_minute
        ),
    }
}
