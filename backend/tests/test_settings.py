"""설정 조회·변경 (SR-F-101~107, 부록 A.3)."""

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Keyword, Setting
from app.schemas.setting import KEYWORD_MAX_COUNT, KEYWORD_MAX_LEN, SUBJECT_MAX_LEN
from app.services.settings_store import DEFAULT_MAX_PER_SOURCE
from tests.test_pipeline import RSS, _seed


def payload(**overrides) -> dict:
    body = {
        "mail_subject": "오늘의 뉴스",
        "mail_to": "me@example.com",
        "max_per_source": 10,
        "keywords": ["AI", "반도체"],
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------- 101


def test_SR_F_101_get_returns_the_four_fields(client: TestClient) -> None:
    body = client.get("/settings").json()
    assert set(body) == {"mail_subject", "mail_to", "max_per_source", "keywords"}


def test_SR_F_101_get_without_a_saved_row_returns_empty_form(
    client: TestClient,
) -> None:
    body = client.get("/settings").json()

    assert body["mail_subject"] == ""
    assert body["mail_to"] == ""
    assert body["max_per_source"] == DEFAULT_MAX_PER_SOURCE
    assert body["keywords"] == []


def test_SR_F_101_get_returns_saved_values(client: TestClient) -> None:
    client.put("/settings", json=payload())

    body = client.get("/settings").json()
    assert body["mail_subject"] == "오늘의 뉴스"
    assert body["mail_to"] == "me@example.com"
    assert body["max_per_source"] == 10
    assert body["keywords"] == ["AI", "반도체"]


def test_SR_F_101_keywords_are_returned_in_a_stable_order(
    client: TestClient,
) -> None:
    client.put("/settings", json=payload(keywords=["반도체", "AI", "백엔드"]))
    first = client.get("/settings").json()["keywords"]
    second = client.get("/settings").json()["keywords"]

    assert first == second
    assert first == sorted(first)


# ---------------------------------------------------------------------- 102


def test_SR_F_102_keyword_at_max_length_is_accepted(client: TestClient) -> None:
    res = client.put("/settings", json=payload(keywords=["가" * KEYWORD_MAX_LEN]))
    assert res.status_code == 200


def test_SR_F_102_keyword_over_max_length_returns_400(client: TestClient) -> None:
    res = client.put("/settings", json=payload(keywords=["가" * (KEYWORD_MAX_LEN + 1)]))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_ERROR"


def test_SR_F_102_blank_keyword_returns_400(client: TestClient) -> None:
    assert client.put("/settings", json=payload(keywords=["   "])).status_code == 400


def test_SR_F_102_exactly_twenty_keywords_is_accepted(client: TestClient) -> None:
    words = [f"kw{i:02d}" for i in range(KEYWORD_MAX_COUNT)]
    assert client.put("/settings", json=payload(keywords=words)).status_code == 200


def test_SR_F_102_more_than_twenty_keywords_returns_400(client: TestClient) -> None:
    words = [f"kw{i:02d}" for i in range(KEYWORD_MAX_COUNT + 1)]
    res = client.put("/settings", json=payload(keywords=words))

    assert res.status_code == 400
    assert "keywords" in res.json()["fields"]


# ---------------------------------------------------------------------- 103


def test_SR_F_103_duplicate_keywords_return_400(client: TestClient) -> None:
    res = client.put("/settings", json=payload(keywords=["AI", "AI"]))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_ERROR"


def test_SR_F_103_duplicate_after_trimming_is_also_rejected(
    client: TestClient,
) -> None:
    assert client.put("/settings", json=payload(keywords=["AI", " AI "])).status_code == 400


def test_SR_F_103_unique_constraint_holds_in_the_store(
    client: TestClient, db_session: Session
) -> None:
    client.put("/settings", json=payload(keywords=["AI", "반도체"]))
    client.put("/settings", json=payload(keywords=["AI", "백엔드"]))

    values = [k.value for k in db_session.query(Keyword).all()]
    assert sorted(values) == ["AI", "백엔드"]
    assert len(values) == len(set(values))


# ---------------------------------------------------------------------- 104


@pytest.mark.parametrize(
    "address", ["plain", "no@tld", "@example.com", "a b@example.com", ""]
)
def test_SR_F_104_invalid_recipient_returns_400(
    client: TestClient, address: str
) -> None:
    res = client.put("/settings", json=payload(mail_to=address))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_ERROR"
    assert "mail_to" in res.json()["fields"]


def test_SR_F_104_valid_recipient_is_accepted(client: TestClient) -> None:
    res = client.put("/settings", json=payload(mail_to="sh.jeong@ck-net.co.kr"))
    assert res.status_code == 200
    assert res.json()["mail_to"] == "sh.jeong@ck-net.co.kr"


# ---------------------------------------------------------------------- 105


@pytest.mark.parametrize("value", [1, 100])
def test_SR_F_105_boundary_values_are_accepted(client: TestClient, value: int) -> None:
    assert client.put("/settings", json=payload(max_per_source=value)).status_code == 200


@pytest.mark.parametrize("value", [0, 101, -1])
def test_SR_F_105_out_of_range_returns_400(client: TestClient, value: int) -> None:
    res = client.put("/settings", json=payload(max_per_source=value))

    assert res.status_code == 400
    assert "max_per_source" in res.json()["fields"]


def test_SR_F_105_non_integer_returns_400(client: TestClient) -> None:
    assert client.put("/settings", json=payload(max_per_source="열개")).status_code == 400


# ---------------------------------------------------------------------- 106


def test_SR_F_106_subject_at_max_length_is_accepted(client: TestClient) -> None:
    res = client.put("/settings", json=payload(mail_subject="뉴" * SUBJECT_MAX_LEN))
    assert res.status_code == 200


def test_SR_F_106_subject_over_max_length_returns_400(client: TestClient) -> None:
    res = client.put("/settings", json=payload(mail_subject="뉴" * (SUBJECT_MAX_LEN + 1)))

    assert res.status_code == 400
    assert "mail_subject" in res.json()["fields"]


def test_SR_F_106_blank_subject_returns_400(client: TestClient) -> None:
    res = client.put("/settings", json=payload(mail_subject="   "))

    assert res.status_code == 400
    assert "mail_subject" in res.json()["fields"]


# ---------------------------------------------------------------------- 107


def test_SR_F_107_put_returns_the_saved_state(client: TestClient) -> None:
    body = client.put("/settings", json=payload()).json()

    assert body["mail_subject"] == "오늘의 뉴스"
    assert body["keywords"] == ["AI", "반도체"]


def test_SR_F_107_second_put_replaces_the_keyword_list(client: TestClient) -> None:
    client.put("/settings", json=payload(keywords=["AI", "반도체"]))
    body = client.put("/settings", json=payload(keywords=["백엔드"])).json()

    assert body["keywords"] == ["백엔드"]


def test_SR_F_107_second_put_updates_the_same_row(
    client: TestClient, db_session: Session
) -> None:
    client.put("/settings", json=payload())
    client.put("/settings", json=payload(mail_subject="바뀐 제목"))

    # 설정은 단일 행이다. 저장할 때마다 행이 늘면 안 된다.
    assert db_session.query(Setting).count() == 1


def test_SR_F_107_saved_keywords_reach_the_next_collection(
    client: TestClient, db_session: Session
) -> None:
    """AC-07. 화면에서 키워드를 추가하면 다음 실행에 반영된다."""
    from app.services.pipeline import run_collection

    _seed(db_session)  # 피드 소스 1개 + 키워드 AI
    client.put("/settings", json=payload(keywords=["반도체", "백엔드"]))

    result = run_collection(
        db_session,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, content=RSS.encode())
            )
        ),
    )

    assert {t.keyword for t in result.targets} == {"반도체", "백엔드"}


def test_SR_F_107_saved_max_per_source_reaches_the_next_collection(
    client: TestClient, db_session: Session
) -> None:
    from app.services.pipeline import run_collection

    _seed(db_session)
    client.put("/settings", json=payload(keywords=["AI"], max_per_source=1))

    result = run_collection(
        db_session,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, content=RSS.encode())
            )
        ),
    )

    assert result.collected_count == 1  # 피드에는 2건이 있다


def test_SR_F_506_saved_recipient_is_used_for_delivery(
    client: TestClient, db_session: Session
) -> None:
    from app.services.pipeline import run_collection

    _seed(db_session)
    client.put("/settings", json=payload(keywords=["AI"], mail_to="to@example.com"))
    sent: list[dict] = []

    run_collection(
        db_session,
        send=True,
        mail_sender=lambda **kw: sent.append(kw),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, content=RSS.encode())
            )
        ),
    )

    assert sent[0]["mail_to"] == "to@example.com"
    assert sent[0]["subject"] == "오늘의 뉴스"
