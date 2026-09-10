"""주소 템플릿 처리 (SR-F-202, 203, 204, 205).

build_collect_url은 이번 슬라이스에서 호출되지 않는다. 수집기(SR-F-3xx)가 쓸 계약을
미리 고정해 두기 위해 여기에 둔다.
"""

from urllib.parse import quote

from app.errors import FeedUrlInvalidError

KEYWORD_PLACEHOLDER = "{keyword}"
_ALLOWED_SCHEMES = ("http://", "https://")


def validate_url_template(url_template: str) -> None:
    """SR-F-202. 불만족 시 FeedUrlInvalidError를 던진다 (400 FEED_URL_INVALID)."""
    if not url_template.startswith(_ALLOWED_SCHEMES):
        raise FeedUrlInvalidError()


def has_keyword_placeholder(url_template: str) -> bool:
    """SR-F-205. 거짓이면 키워드 수와 무관하게 1회만 조회한다."""
    return KEYWORD_PLACEHOLDER in url_template


def build_collect_url(url_template: str, keyword: str) -> str:
    """SR-F-203 + SR-F-204: 치환하고 키워드를 URL 인코딩한다.

    quote_plus(공백 -> '+')가 아니라 quote(safe="", 공백 -> '%20')를 쓴다.
    둘 다 동작하지만 하나로 고정해야 수집기가 정해진 계약을 물려받는다.
    """
    return url_template.replace(KEYWORD_PLACEHOLDER, quote(keyword, safe=""))
