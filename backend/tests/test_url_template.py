"""주소 템플릿 헬퍼 단위 테스트 (SR-F-202~205)."""

import pytest

from app.errors import FeedUrlInvalidError
from app.services.url_template import (
    build_collect_url,
    has_keyword_placeholder,
    validate_url_template,
)


@pytest.mark.parametrize(
    "url_template",
    ["http://example.com/rss", "https://example.com/rss"],
)
def test_SR_F_202_http_and_https_are_accepted(url_template: str) -> None:
    validate_url_template(url_template)


@pytest.mark.parametrize(
    "url_template",
    ["ftp://example.com/rss", "example.com/rss", "//example.com/rss", ""],
)
def test_SR_F_202_non_http_scheme_raises(url_template: str) -> None:
    with pytest.raises(FeedUrlInvalidError):
        validate_url_template(url_template)


def test_SR_F_203_build_collect_url_substitutes_placeholder() -> None:
    url = build_collect_url("https://example.com/rss?q={keyword}", "AI")
    assert url == "https://example.com/rss?q=AI"


def test_SR_F_204_build_collect_url_encodes_korean_keyword() -> None:
    url = build_collect_url("https://example.com/rss?q={keyword}", "반도체")
    assert url == "https://example.com/rss?q=%EB%B0%98%EB%8F%84%EC%B2%B4"


def test_SR_F_204_build_collect_url_encodes_space_as_percent_20() -> None:
    # quote_plus('+')가 아니라 quote(safe='')('%20')로 고정한다.
    url = build_collect_url("https://example.com/rss?q={keyword}", "생성형 AI")
    assert url == "https://example.com/rss?q=%EC%83%9D%EC%84%B1%ED%98%95%20AI"


def test_SR_F_205_has_keyword_placeholder() -> None:
    assert has_keyword_placeholder("https://example.com/rss?q={keyword}") is True
    assert has_keyword_placeholder("https://example.com/rss") is False


def test_SR_F_205_build_collect_url_returns_template_unchanged() -> None:
    template = "https://example.com/rss"
    assert build_collect_url(template, "AI") == template
