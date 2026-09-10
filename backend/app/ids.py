"""식별자 생성. SRS 5.1의 문자열(26) = ULID."""

from ulid import ULID


def new_ulid() -> str:
    """26자 Crockford base32 ULID를 반환한다."""
    return str(ULID())
