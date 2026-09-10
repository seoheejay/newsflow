"""피드 소스 CRUD API 테스트 (SR-F-201~209)."""

import pytest
from fastapi.testclient import TestClient

from app.models import Article, FeedSource
from tests.conftest import make_payload


def test_SR_F_201_create_stores_all_fields_and_returns_201(client: TestClient) -> None:
    payload = make_payload()
    res = client.post("/feed-sources", json=payload)

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == payload["name"]
    assert body["url_template"] == payload["url_template"]
    assert body["sort_order"] == payload["sort_order"]
    assert body["is_active"] is True


def test_SR_F_201_create_returns_26_char_ulid_id(client: TestClient) -> None:
    res = client.post("/feed-sources", json=make_payload())
    assert len(res.json()["id"]) == 26


def test_SR_F_201_user_id_is_not_exposed_in_response(client: TestClient) -> None:
    res = client.post("/feed-sources", json=make_payload())
    assert set(res.json()) == {"id", "name", "url_template", "sort_order", "is_active"}


def test_SR_F_202_non_http_scheme_returns_400_feed_url_invalid(
    client: TestClient,
) -> None:
    res = client.post(
        "/feed-sources", json=make_payload(url_template="ftp://example.com/rss")
    )
    assert res.status_code == 400
    assert res.json()["code"] == "FEED_URL_INVALID"


def test_SR_F_202_update_with_invalid_template_returns_400_feed_url_invalid(
    client: TestClient,
) -> None:
    created = client.post("/feed-sources", json=make_payload()).json()
    res = client.put(
        f"/feed-sources/{created['id']}",
        json=make_payload(url_template="ftp://example.com/rss"),
    )
    assert res.status_code == 400
    assert res.json()["code"] == "FEED_URL_INVALID"


def test_SR_F_205_template_without_placeholder_is_registrable(
    client: TestClient,
) -> None:
    res = client.post(
        "/feed-sources",
        json=make_payload(name="공지", url_template="https://example.com/rss"),
    )
    assert res.status_code == 201


def test_SR_F_206_duplicate_name_returns_409_duplicate_name(
    client: TestClient,
) -> None:
    client.post("/feed-sources", json=make_payload())
    res = client.post("/feed-sources", json=make_payload())

    assert res.status_code == 409
    assert res.json()["code"] == "DUPLICATE_NAME"


def test_SR_F_206_update_to_existing_name_returns_409(client: TestClient) -> None:
    client.post("/feed-sources", json=make_payload(name="구글"))
    other = client.post("/feed-sources", json=make_payload(name="지디넷")).json()

    res = client.put(f"/feed-sources/{other['id']}", json=make_payload(name="구글"))
    assert res.status_code == 409
    assert res.json()["code"] == "DUPLICATE_NAME"


def test_SR_F_206_update_keeping_own_name_returns_200(client: TestClient) -> None:
    created = client.post("/feed-sources", json=make_payload()).json()

    res = client.put(
        f"/feed-sources/{created['id']}", json=make_payload(sort_order=9)
    )
    assert res.status_code == 200
    assert res.json()["sort_order"] == 9


def test_SR_F_207_is_active_false_is_persisted(client: TestClient) -> None:
    created = client.post("/feed-sources", json=make_payload()).json()

    res = client.put(
        f"/feed-sources/{created['id']}", json=make_payload(is_active=False)
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False
    assert client.get("/feed-sources").json()["items"][0]["is_active"] is False


def test_SR_F_208_delete_returns_204(client: TestClient) -> None:
    created = client.post("/feed-sources", json=make_payload()).json()

    res = client.delete(f"/feed-sources/{created['id']}")
    assert res.status_code == 204
    assert res.content == b""
    assert client.get("/feed-sources").json()["total_count"] == 0


def test_SR_F_208_feed_sources_and_articles_have_no_foreign_keys() -> None:
    # 기사가 피드 소스 삭제에 영향받지 않는 근거는 FK가 없다는 구조 자체다.
    assert FeedSource.__table__.foreign_keys == set()
    assert Article.__table__.foreign_keys == set()


def test_SR_F_209_list_ordered_by_sort_order_then_name(client: TestClient) -> None:
    client.post("/feed-sources", json=make_payload(name="ddd", sort_order=5))
    client.post("/feed-sources", json=make_payload(name="aaa", sort_order=5))
    client.post("/feed-sources", json=make_payload(name="zzz", sort_order=1))

    names = [item["name"] for item in client.get("/feed-sources").json()["items"]]
    assert names == ["zzz", "aaa", "ddd"]


def test_SR_I_304_list_returns_envelope_with_total_count_page_items_per_page(
    client: TestClient,
) -> None:
    client.post("/feed-sources", json=make_payload())

    body = client.get("/feed-sources").json()
    assert set(body) == {"total_count", "page", "items_per_page", "items"}
    assert body["total_count"] == 1
    assert body["page"] == 1
    assert body["items_per_page"] == 100


def test_SR_I_304_empty_table_returns_zero_total_count_and_empty_items(
    client: TestClient,
) -> None:
    res = client.get("/feed-sources")
    assert res.status_code == 200
    assert res.json()["total_count"] == 0
    assert res.json()["items"] == []


def test_SR_D_202_feed_source_name_unique_constraint_exists() -> None:
    names = {c.name for c in FeedSource.__table__.constraints}
    assert "uq_feed_sources_name" in names


def test_SR_D_201_article_link_hash_unique_constraint_exists() -> None:
    names = {c.name for c in Article.__table__.constraints}
    assert "uq_articles_link_hash" in names


def test_SR_D_205_korean_and_emoji_name_round_trips(client: TestClient) -> None:
    res = client.post("/feed-sources", json=make_payload(name="테스트🚀"))
    assert res.status_code == 201
    assert res.json()["name"] == "테스트🚀"


def test_SR_I_302_response_keys_are_snake_case(client: TestClient) -> None:
    res = client.post("/feed-sources", json=make_payload())
    assert all(key == key.lower() and "-" not in key for key in res.json())


def test_SR_I_305_invalid_body_returns_400_with_code_message_fields(
    client: TestClient,
) -> None:
    res = client.post("/feed-sources", json=make_payload(name="   "))

    assert res.status_code == 400  # FastAPI 기본값 422가 아니다
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"]
    assert body["fields"] == ["name"]


def test_SR_I_305_success_response_has_no_fields_key(client: TestClient) -> None:
    res = client.post("/feed-sources", json=make_payload(url_template="ftp://x/rss"))
    # 입력값 오류가 아닌 오류에는 fields 키 자체가 없어야 한다.
    assert "fields" not in res.json()


@pytest.mark.parametrize("method", ["put", "delete"])
def test_SR_I_305_unknown_id_returns_404_not_found(
    client: TestClient, method: str
) -> None:
    kwargs = {"json": make_payload()} if method == "put" else {}
    res = getattr(client, method)("/feed-sources/NOPE", **kwargs)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_SR_I_306_preflight_allows_localhost_5173(client: TestClient) -> None:
    res = client.options(
        "/feed-sources",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
