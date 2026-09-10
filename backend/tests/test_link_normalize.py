"""링크 정규화 단위 테스트 (SR-F-401~403)."""

import pytest

from app.services.link_normalize import TRACKING_PARAMS, link_hash, normalize_link


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 스킴·호스트 소문자화
        ("HTTPS://Example.COM/a", "https://example.com/a"),
        # 경로 끝 슬래시 제거
        ("https://example.com/a/", "https://example.com/a"),
        ("https://example.com/", "https://example.com"),
        # 프래그먼트 제거
        ("https://example.com/a#section", "https://example.com/a"),
        # 경로 대소문자는 건드리지 않는다 (서버가 구분할 수 있다)
        ("https://example.com/Path", "https://example.com/Path"),
    ],
)
def test_SR_F_402_normalize_link(raw: str, expected: str) -> None:
    assert normalize_link(raw) == expected


@pytest.mark.parametrize("param", sorted(TRACKING_PARAMS))
def test_SR_F_403_tracking_params_are_removed(param: str) -> None:
    assert normalize_link(f"https://example.com/a?{param}=x") == "https://example.com/a"


def test_SR_F_403_tracking_param_list_matches_appendix_c() -> None:
    assert TRACKING_PARAMS == {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "oc",
    }


def test_SR_F_403_non_tracking_params_are_kept() -> None:
    url = "https://example.com/a?id=7&utm_source=news&page=2"
    assert normalize_link(url) == "https://example.com/a?id=7&page=2"


def test_SR_F_402_tracking_params_only_leaves_no_query() -> None:
    assert normalize_link("https://example.com/a?utm_source=x&fbclid=y") == (
        "https://example.com/a"
    )


def test_SR_F_401_hash_is_64_char_sha256() -> None:
    value = link_hash("https://example.com/a")
    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")


def test_SR_F_401_links_differing_only_by_tracking_share_a_hash() -> None:
    # 이 성질이 SR-F-404/405의 전제다.
    a = link_hash("https://example.com/news/1?utm_source=daily#top")
    b = link_hash("HTTPS://Example.com/news/1/")
    assert a == b


def test_SR_F_401_different_links_differ() -> None:
    assert link_hash("https://example.com/1") != link_hash("https://example.com/2")
