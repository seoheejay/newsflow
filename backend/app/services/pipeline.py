"""수집 파이프라인 (SRS 부록 B.1의 5~14단계).

Celery에 묶여 있지 않다. 이후 작업 처리기는 run_collection()을 호출하고
그 결과로 실행 상태만 갱신하면 된다(SR-F-703).

이번 범위 밖: 메일 발송(SR-F-5xx), 실행 이력(SR-F-7xx), 스케줄(SR-F-8xx).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.errors import EmailSendFailedError
from app.models import FeedSource
from app.services import mailer, processing, settings_store
from app.services.collector import (
    CollectedItem,
    CollectTarget,
    NodeLog,
    build_targets,
    collect,
)
from app.services.settings_store import DEFAULT_MAIL_SUBJECT, DEFAULT_MAX_PER_SOURCE

__all__ = ["CollectionResult", "run_collection", "DEFAULT_MAX_PER_SOURCE"]


@dataclass
class CollectionResult:
    targets: list[CollectTarget] = field(default_factory=list)
    node_logs: list[NodeLog] = field(default_factory=list)
    collected_count: int = 0  # 수집 건수 (중복 제거 전)
    deduped_count: int = 0  # 실행 내 중복 제거 후
    new_items: list[CollectedItem] = field(default_factory=list)  # 전달 대상
    failed: bool = False  # SR-F-310, SR-F-508
    stored: bool = False
    sent: bool = False
    error: str | None = None  # 실패 사유 (SR-F-703의 error에 들어갈 값)

    @property
    def new_count(self) -> int:
        return len(self.new_items)


def load_active_feed_sources(
    db: Session, user_id: str = DEFAULT_USER_ID
) -> list[tuple[str, str, int]]:
    """SR-F-207. 활성 소스만 수집 대상이다."""
    rows = db.execute(
        select(FeedSource.name, FeedSource.url_template, FeedSource.sort_order)
        .where(FeedSource.is_active.is_(True), FeedSource.user_id == user_id)
        .order_by(FeedSource.sort_order.asc(), FeedSource.name.asc())
    ).all()
    return [(r.name, r.url_template, r.sort_order) for r in rows]


def load_mail_settings(
    db: Session, user_id: str = DEFAULT_USER_ID
) -> tuple[str, str | None]:
    """(제목, 수신자). 제목이 비어 있으면 기본값을, 수신자가 없으면 None을 준다."""
    data = settings_store.load_settings(db, user_id)
    return (data.mail_subject or DEFAULT_MAIL_SUBJECT), (data.mail_to or None)


def run_collection(
    db: Session,
    *,
    keywords: list[str] | None = None,
    max_per_source: int | None = None,
    store: bool = False,
    send: bool = False,
    mail_to: str | None = None,
    mail_subject: str | None = None,
    mail_sender=None,
    user_id: str = DEFAULT_USER_ID,
    **collect_kwargs,
) -> CollectionResult:
    """부록 B.1의 5~17단계를 수행한다.

    keywords/max_per_source를 주면 DB 값 대신 쓴다(스크립트 실행용).
    store=True면 전달 대상을 저장한다(SR-F-601).
    send=True면 메일을 발송한다(SR-F-506). mail_sender는 테스트용 주입점이다.
    """
    result = CollectionResult()

    # 5단계: 설정 및 활성 피드 소스 조회
    stored = settings_store.load_settings(db, user_id)
    if keywords is None:
        keywords = stored.keywords
    if max_per_source is None:
        max_per_source = stored.max_per_source
    feed_sources = load_active_feed_sources(db, user_id)

    # 6단계: 수집 주소 생성 (SR-F-301)
    result.targets = build_targets(keywords, feed_sources)
    if not result.targets:
        return result

    # 7~9단계: 조회·파싱·건수 제한 (SR-F-302, 306, 307, 308, 309)
    outcome = collect(result.targets, max_per_source=max_per_source, **collect_kwargs)
    result.node_logs = outcome.node_logs
    result.collected_count = len(outcome.items)

    # SR-F-310: 전부 실패면 실행 실패. 이후 단계를 진행하지 않는다.
    if outcome.all_failed:
        result.failed = True
        result.error = "전체 주소 수집 실패"
        return result

    # 10~11단계: 정규화·해시는 수집 시점에 끝났고, 여기서 실행 내 중복을 제거한다 (SR-F-404)
    deduped = processing.dedupe_within_run(outcome.items)
    result.deduped_count = len(deduped)

    # 12단계: 저장소 대비 신규 판정 (SR-F-405)
    fresh = processing.select_new_items(db, deduped)

    # 14단계: 정렬 (SR-F-406, 407)
    result.new_items = processing.sort_for_delivery(fresh)

    # 13단계: 신규 기사 저장 (SR-F-601). 옵트인이다.
    if store and result.new_items:
        collected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add_all(
            processing.to_articles(
                result.new_items, collected_at=collected_at, user_id=user_id
            )
        )
        db.commit()
        result.stored = True

    # 15단계: 신규 0건이면 발송을 생략하고 success로 끝낸다 (SR-F-507).
    if not result.new_items:
        return result

    # 16단계: HTML 본문 생성 및 발송 (SR-F-501, 506)
    if send:
        subject, configured_to = load_mail_settings(db, user_id)
        recipient = mail_to or configured_to
        subject = mail_subject or subject

        if not recipient:
            result.failed = True
            result.error = "수신자가 없다. 설정에 mail_to를 넣거나 인자로 넘길 것"
            return result

        sender = mail_sender or mailer.send_mail
        try:
            sender(subject=subject, mail_to=recipient, items=result.new_items)
        except EmailSendFailedError as exc:
            # SR-F-508: 발송 실패는 실행 실패이고 사유를 남긴다.
            result.failed = True
            result.error = exc.message
            return result
        result.sent = True

    return result
