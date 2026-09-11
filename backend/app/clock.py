"""시각. 보관은 UTC (SR-D-203)."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """DB 컬럼이 naive DateTime이라 tzinfo를 떼고 돌려준다.

    DB 컨테이너가 TZ=Asia/Seoul로 뜨므로 server_default=func.now()를 쓰면
    KST가 들어간다. 시각은 항상 파이썬 쪽에서 만든다.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
