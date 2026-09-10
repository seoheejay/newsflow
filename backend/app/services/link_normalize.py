"""링크 정규화와 해시 (SR-F-401, 402, 403).

중복 판단의 기준이다. 여기서 같은 값이 나오면 같은 기사로 취급한다(SR-F-404, 405).
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# SR-F-403 / 부록 C.1. 목록이 바뀌면 SRS를 함께 개정한다.
TRACKING_PARAMS = frozenset(
    {
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
)


def normalize_link(link: str) -> str:
    """SR-F-402의 네 가지만 수행한다.

    스킴·호스트 소문자화, 경로 끝 슬래시 제거, 프래그먼트 제거, 추적 파라미터 제거.

    질의 파라미터의 순서는 바꾸지 않는다. 명세에 없는 정규화를 더하면 기존 운영 방식과의
    결과 대조(AC-01)에서 원인을 짚기 어려워진다.
    """
    parts = urlsplit(link.strip())

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    # 경로 끝 슬래시 제거. 루트("/")는 빈 문자열이 된다.
    path = parts.path.rstrip("/")

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_PARAMS
    ]
    query = urlencode(kept)

    # 네 번째 인자를 비워 프래그먼트를 제거한다.
    return urlunsplit((scheme, netloc, path, query, ""))


def link_hash(link: str) -> str:
    """SR-F-401. 정규화한 링크의 SHA-256 16진 문자열(64자)."""
    return hashlib.sha256(normalize_link(link).encode("utf-8")).hexdigest()
