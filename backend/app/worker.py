"""Celery 애플리케이션 (SRS 2.1의 작업 처리기).

Windows에서 워커를 띄울 때는 --pool=solo가 필요하다. 기본 prefork 풀은
fork()에 기대는데 Windows에는 fork가 없다.

    poetry run celery -A app.worker.celery_app worker --loglevel=info --pool=solo
"""

from celery import Celery

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
    # 보관은 UTC(SR-D-203). 표시 시점에만 Asia/Seoul로 바꾼다.
    timezone="UTC",
    enable_utc=True,
    # 작업을 하나씩만 가져간다. 수집은 동시 실행을 막고 있으므로(SR-F-705)
    # 미리 쌓아둘 이유가 없다.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
