"""수집 결과 가공 (SR-F-404~407).

SR-F-405가 본 릴리스의 핵심 개선 항목이다 — 이전 실행에서 이미 전달한 기사를
다시 전달하지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article
from app.services.collector import CollectedItem

# MySQL의 파라미터 수 제한에 걸리지 않도록 IN 절을 나눈다.
_IN_CHUNK = 1000


def dedupe_within_run(items: list[CollectedItem]) -> list[CollectedItem]:
    """SR-F-404. 같은 링크 해시는 최초 1건만 남긴다.

    collect()가 targets 순서를 유지하므로 "최초"가 결정적이다.
    """
    seen: set[str] = set()
    kept: list[CollectedItem] = []
    for item in items:
        if item.link_hash in seen:
            continue
        seen.add(item.link_hash)
        kept.append(item)
    return kept


def existing_link_hashes(db: Session, hashes: list[str]) -> set[str]:
    """저장소에 이미 있는 링크 해시를 돌려준다."""
    found: set[str] = set()
    for start in range(0, len(hashes), _IN_CHUNK):
        chunk = hashes[start : start + _IN_CHUNK]
        rows = db.scalars(
            select(Article.link_hash).where(Article.link_hash.in_(chunk))
        ).all()
        found.update(rows)
    return found


def select_new_items(db: Session, items: list[CollectedItem]) -> list[CollectedItem]:
    """SR-F-405. 저장소에 같은 링크 해시가 있으면 전달 대상에서 뺀다."""
    if not items:
        return []
    known = existing_link_hashes(db, [item.link_hash for item in items])
    return [item for item in items if item.link_hash not in known]


def _sort_key(item: CollectedItem) -> tuple:
    """SR-F-406 + SR-F-407.

    키워드 오름차순 → 피드 소스 정렬 순서 오름차순 → 발행일시 내림차순.
    발행일시가 없는 기사는 같은 그룹의 마지막에 둔다.
    """
    missing = item.published_at is None
    # 내림차순을 오름차순 정렬로 표현하기 위해 타임스탬프를 음수로 만든다.
    stamp = 0.0 if item.published_at is None else -item.published_at.timestamp()
    return (item.keyword, item.sort_order, missing, stamp)


def sort_for_delivery(items: list[CollectedItem]) -> list[CollectedItem]:
    """SR-F-406, 407."""
    return sorted(items, key=_sort_key)


def to_articles(
    items: list[CollectedItem], *, collected_at: datetime, user_id: str
) -> list[Article]:
    """전달 대상 항목을 Article 행으로 만든다 (SR-F-601 저장에 쓰인다)."""
    from app.ids import new_ulid

    return [
        Article(
            id=new_ulid(),
            title=item.title,
            link=item.link,
            link_hash=item.link_hash,
            keyword=item.keyword,
            site=item.site,
            published_at=item.published_at,
            collected_at=collected_at,
            user_id=user_id,
        )
        for item in items
    ]
