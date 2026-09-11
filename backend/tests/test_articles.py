"""기사 조회 (SR-F-602~606, 부록 A.2/A.3)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.models import Article
from app.routers.articles import DEFAULT_ITEMS_PER_PAGE, MAX_ITEMS_PER_PAGE
from app.services.link_normalize import link_hash


def _article(
    db: Session,
    *,
    n: int,
    keyword: str = "AI",
    site: str = "구글",
    collected: datetime | None = None,
    published: datetime | None = None,
) -> Article:
    link = f"https://example.com/{n}"
    row = Article(
        id=f"01{n:024d}",
        title=f"기사 {n}",
        link=link,
        link_hash=link_hash(link),
        keyword=keyword,
        site=site,
        published_at=published,
        collected_at=collected or datetime(2026, 9, 10, 0, 0),
        user_id=DEFAULT_USER_ID,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------- 606


def test_SR_F_606_empty_store_returns_200_and_empty_list(client: TestClient) -> None:
    res = client.get("/articles")

    assert res.status_code == 200
    assert res.json()["total_count"] == 0
    assert res.json()["items"] == []


def test_SR_F_606_no_match_returns_200_and_empty_list(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, keyword="AI")

    body = client.get("/articles", params={"keyword": "없는키워드"}).json()
    assert body["total_count"] == 0
    assert body["items"] == []


# ------------------------------------------------------------------ A.3 형태


def test_SR_I_304_response_uses_the_envelope(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1)

    body = client.get("/articles").json()
    assert set(body) == {"total_count", "page", "items_per_page", "items"}


def test_A3_item_fields_match_the_appendix(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1)

    item = client.get("/articles").json()["items"][0]
    assert set(item) == {
        "id",
        "title",
        "link",
        "keyword",
        "site",
        "published_at",
        "collected_at",
    }
    # 내부 컬럼은 내보내지 않는다
    assert "link_hash" not in item
    assert "user_id" not in item
    assert "summary" not in item


def test_SR_I_303_datetimes_are_iso_utc(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, collected=datetime(2026, 9, 10, 5, 12))

    item = client.get("/articles").json()["items"][0]
    assert item["collected_at"].startswith("2026-09-10T05:12:00")


def test_SR_F_304_missing_published_at_is_null(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, published=None)
    assert client.get("/articles").json()["items"][0]["published_at"] is None


# ---------------------------------------------------------------------- 602


def test_SR_F_602_default_page_size_is_twenty(
    client: TestClient, db_session: Session
) -> None:
    for n in range(25):
        _article(db_session, n=n)

    body = client.get("/articles").json()
    assert body["items_per_page"] == DEFAULT_ITEMS_PER_PAGE
    assert len(body["items"]) == 20
    assert body["total_count"] == 25  # 총계는 페이지가 아니라 전체다


def test_SR_F_602_second_page_returns_the_remainder(
    client: TestClient, db_session: Session
) -> None:
    for n in range(25):
        _article(db_session, n=n)

    body = client.get("/articles", params={"page": 2}).json()
    assert body["page"] == 2
    assert len(body["items"]) == 5


def test_SR_F_602_pages_do_not_overlap(
    client: TestClient, db_session: Session
) -> None:
    for n in range(25):
        _article(db_session, n=n)

    first = {i["id"] for i in client.get("/articles", params={"page": 1}).json()["items"]}
    second = {i["id"] for i in client.get("/articles", params={"page": 2}).json()["items"]}
    assert first & second == set()


def test_SR_F_602_max_page_size_is_accepted(client: TestClient) -> None:
    res = client.get("/articles", params={"items_per_page": MAX_ITEMS_PER_PAGE})
    assert res.status_code == 200


def test_SR_F_602_over_max_page_size_returns_400(client: TestClient) -> None:
    res = client.get("/articles", params={"items_per_page": MAX_ITEMS_PER_PAGE + 1})

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_ERROR"
    assert "items_per_page" in res.json()["fields"]


def test_SR_F_602_page_zero_returns_400(client: TestClient) -> None:
    res = client.get("/articles", params={"page": 0})
    assert res.status_code == 400
    assert "page" in res.json()["fields"]


# ---------------------------------------------------------------------- 603


def test_SR_F_603_filters_by_keyword(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, keyword="AI")
    _article(db_session, n=2, keyword="반도체")

    body = client.get("/articles", params={"keyword": "반도체"}).json()
    assert body["total_count"] == 1
    assert body["items"][0]["keyword"] == "반도체"


def test_SR_F_603_filters_by_site(client: TestClient, db_session: Session) -> None:
    _article(db_session, n=1, site="구글")
    _article(db_session, n=2, site="지디넷")

    body = client.get("/articles", params={"site": "지디넷"}).json()
    assert body["total_count"] == 1
    assert body["items"][0]["site"] == "지디넷"


def test_SR_F_603_keyword_match_is_exact_not_partial(
    client: TestClient, db_session: Session
) -> None:
    # 부록 A.2가 "키워드 완전 일치"라고 못박았다
    _article(db_session, n=1, keyword="AI반도체")

    assert client.get("/articles", params={"keyword": "AI"}).json()["total_count"] == 0


def test_SR_F_603_filters_combine(client: TestClient, db_session: Session) -> None:
    _article(db_session, n=1, keyword="AI", site="구글")
    _article(db_session, n=2, keyword="AI", site="지디넷")
    _article(db_session, n=3, keyword="반도체", site="구글")

    body = client.get("/articles", params={"keyword": "AI", "site": "구글"}).json()
    assert body["total_count"] == 1


@pytest.mark.parametrize("field", ["keyword", "site"])
def test_SR_F_603_empty_filter_means_all(
    client: TestClient, db_session: Session, field: str
) -> None:
    _article(db_session, n=1)
    _article(db_session, n=2)

    assert client.get("/articles", params={field: ""}).json()["total_count"] == 2


# ---------------------------------------------------------------------- 604


def test_SR_F_604_from_is_inclusive_in_kst(
    client: TestClient, db_session: Session
) -> None:
    # KST 2026-09-10 00:00 == UTC 2026-09-09 15:00
    _article(db_session, n=1, collected=datetime(2026, 9, 9, 15, 0))  # KST 09-10 00:00
    _article(db_session, n=2, collected=datetime(2026, 9, 9, 14, 59))  # KST 09-09 23:59

    body = client.get("/articles", params={"from": "2026-09-10"}).json()
    assert body["total_count"] == 1
    assert body["items"][0]["id"].endswith("1")


def test_SR_F_604_to_is_inclusive_in_kst(
    client: TestClient, db_session: Session
) -> None:
    # KST 2026-09-10 23:59:59 == UTC 2026-09-10 14:59:59
    _article(db_session, n=1, collected=datetime(2026, 9, 10, 14, 59, 59))
    _article(db_session, n=2, collected=datetime(2026, 9, 10, 15, 0, 0))  # KST 09-11

    body = client.get("/articles", params={"to": "2026-09-10"}).json()
    assert body["total_count"] == 1
    assert body["items"][0]["id"].endswith("1")


def test_SR_F_604_same_day_from_and_to_covers_that_kst_day(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, collected=datetime(2026, 9, 9, 15, 0))  # KST 09-10 00:00
    _article(db_session, n=2, collected=datetime(2026, 9, 10, 14, 59))  # KST 09-10 23:59
    _article(db_session, n=3, collected=datetime(2026, 9, 10, 15, 0))  # KST 09-11 00:00

    body = client.get(
        "/articles", params={"from": "2026-09-10", "to": "2026-09-10"}
    ).json()
    assert body["total_count"] == 2


def test_SR_F_604_invalid_date_returns_400(client: TestClient) -> None:
    res = client.get("/articles", params={"from": "어제"})

    assert res.status_code == 400
    assert "from" in res.json()["fields"]


# ---------------------------------------------------------------------- 605


def test_SR_F_605_ordered_by_collected_at_desc(
    client: TestClient, db_session: Session
) -> None:
    _article(db_session, n=1, collected=datetime(2026, 9, 8, 0, 0))
    _article(db_session, n=2, collected=datetime(2026, 9, 10, 0, 0))
    _article(db_session, n=3, collected=datetime(2026, 9, 9, 0, 0))

    order = [i["collected_at"] for i in client.get("/articles").json()["items"]]
    assert order == sorted(order, reverse=True)


def test_SR_F_605_ties_are_broken_deterministically(
    client: TestClient, db_session: Session
) -> None:
    same = datetime(2026, 9, 10, 0, 0)
    for n in range(5):
        _article(db_session, n=n, collected=same)

    first = [i["id"] for i in client.get("/articles").json()["items"]]
    second = [i["id"] for i in client.get("/articles").json()["items"]]
    assert first == second
