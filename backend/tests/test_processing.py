"""가공 단위 테스트 (SR-F-404~407).

파이프라인 통합과 AC-04는 test_pipeline.py에 있다.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Article
from app.services.collector import CollectedItem
from app.services.link_normalize import link_hash
from app.services.processing import (
    dedupe_within_run,
    select_new_items,
    sort_for_delivery,
    to_articles,
)


def _item(
    link: str,
    *,
    keyword: str = "AI",
    site: str = "구글",
    order: int = 1,
    published: datetime | None = None,
    title: str = "제목",
) -> CollectedItem:
    return CollectedItem(
        title=title,
        link=link,
        link_hash=link_hash(link),
        keyword=keyword,
        site=site,
        sort_order=order,
        published_at=published,
    )


# ------------------------------------------------------------------------ 404


def test_SR_F_404_same_link_hash_keeps_only_the_first() -> None:
    items = [
        _item("https://example.com/1", title="처음"),
        _item("https://example.com/1?utm_source=x", title="나중"),  # 정규화하면 같다
        _item("https://example.com/2", title="다른 기사"),
    ]
    kept = dedupe_within_run(items)

    assert [i.title for i in kept] == ["처음", "다른 기사"]


def test_SR_F_404_empty_input() -> None:
    assert dedupe_within_run([]) == []


# ------------------------------------------------------------------------ 405


def test_SR_F_405_items_already_in_store_are_excluded(db_session: Session) -> None:
    db_session.add(
        Article(
            id="01AAAAAAAAAAAAAAAAAAAAAAAA",
            title="이미 보낸 기사",
            link="https://example.com/old",
            link_hash=link_hash("https://example.com/old"),
            keyword="AI",
            site="구글",
            published_at=None,
            collected_at=datetime(2026, 9, 9, 0, 0),
            user_id="00000000000000000000000000",
        )
    )
    db_session.commit()

    items = [_item("https://example.com/old"), _item("https://example.com/new")]
    fresh = select_new_items(db_session, items)

    assert [i.link for i in fresh] == ["https://example.com/new"]


def test_SR_F_405_empty_store_returns_everything(db_session: Session) -> None:
    items = [_item("https://example.com/1"), _item("https://example.com/2")]
    assert len(select_new_items(db_session, items)) == 2


def test_SR_F_405_empty_input(db_session: Session) -> None:
    assert select_new_items(db_session, []) == []


# ------------------------------------------------------------------- 406, 407


def test_SR_F_406_sorts_by_keyword_then_sort_order_then_published_desc() -> None:
    items = [
        _item("https://e.com/4", keyword="반도체", order=1, published=datetime(2026, 9, 1)),
        _item("https://e.com/2", keyword="AI", order=1, published=datetime(2026, 9, 1)),
        _item("https://e.com/3", keyword="AI", order=2, published=datetime(2026, 9, 9)),
        _item("https://e.com/1", keyword="AI", order=1, published=datetime(2026, 9, 8)),
    ]
    order = [i.link for i in sort_for_delivery(items)]

    assert order == [
        "https://e.com/1",  # AI  / 1 / 09-08
        "https://e.com/2",  # AI  / 1 / 09-01
        "https://e.com/3",  # AI  / 2
        "https://e.com/4",  # 반도체
    ]


def test_SR_F_407_missing_published_goes_last_within_its_group() -> None:
    items = [
        _item("https://e.com/none", published=None),
        _item("https://e.com/old", published=datetime(2026, 9, 1)),
        _item("https://e.com/new", published=datetime(2026, 9, 9)),
    ]
    order = [i.link for i in sort_for_delivery(items)]

    assert order == ["https://e.com/new", "https://e.com/old", "https://e.com/none"]


def test_SR_F_407_missing_published_is_last_only_within_its_own_group() -> None:
    items = [
        _item("https://e.com/b-dated", keyword="반도체", published=datetime(2026, 9, 1)),
        _item("https://e.com/a-none", keyword="AI", published=None),
    ]
    # 날짜 없는 AI 기사가 전체 마지막이 아니라 AI 그룹의 마지막이어야 한다.
    assert [i.link for i in sort_for_delivery(items)] == [
        "https://e.com/a-none",
        "https://e.com/b-dated",
    ]


def test_SR_F_406_empty_input() -> None:
    assert sort_for_delivery([]) == []


# ------------------------------------------------------------------------ 601


def test_SR_F_601_to_articles_maps_fields(db_session: Session) -> None:
    collected_at = datetime(2026, 9, 10, 12, 0)
    rows = to_articles(
        [_item("https://e.com/1", title="제목", published=datetime(2026, 9, 8))],
        collected_at=collected_at,
        user_id="00000000000000000000000000",
    )
    row = rows[0]

    assert len(row.id) == 26
    assert row.title == "제목"
    assert row.link_hash == link_hash("https://e.com/1")
    assert row.collected_at == collected_at
    assert row.summary is None  # UR-DAT-06: 이번 릴리스 미사용
