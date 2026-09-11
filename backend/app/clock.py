"""시각. 보관은 UTC (SR-D-203), 표시와 일자 해석은 Asia/Seoul."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

# SR-F-504. 표시 시점에만 쓴다.
KST = ZoneInfo("Asia/Seoul")


def utcnow() -> datetime:
    """DB 컬럼이 naive DateTime이라 tzinfo를 떼고 돌려준다.

    DB 컨테이너가 TZ=Asia/Seoul로 뜨므로 server_default=func.now()를 쓰면
    KST가 들어간다. 시각은 항상 파이썬 쪽에서 만든다.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def kst_day_start_utc(day: date) -> datetime:
    """KST 그 날의 00:00:00을 UTC로 (포함 시작)."""
    return _to_utc_naive(datetime.combine(day, time.min, tzinfo=KST))


def kst_day_end_utc(day: date) -> datetime:
    """KST 그 날의 23:59:59.999999를 UTC로 (포함 종료)."""
    return _to_utc_naive(datetime.combine(day, time.max, tzinfo=KST))
