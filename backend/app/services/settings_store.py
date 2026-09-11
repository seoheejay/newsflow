"""설정과 키워드의 읽기·쓰기 (SR-F-101~107).

API 라우터와 수집 파이프라인이 같은 함수를 쓴다. 두 곳이 각자 조회하면
기본값 처리가 갈라진다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.ids import new_ulid
from app.models import Keyword, Setting

# Setting 행이 아직 없을 때 쓰는 값. 부록 A.3의 예시와 같다.
DEFAULT_MAX_PER_SOURCE = 10
DEFAULT_MAIL_SUBJECT = "오늘의 뉴스"
# SR-F-802. Asia/Seoul 08:00.
DEFAULT_SCHEDULE_HOUR = 8
DEFAULT_SCHEDULE_MINUTE = 0


@dataclass
class SettingsData:
    mail_subject: str = ""
    mail_to: str = ""
    max_per_source: int = DEFAULT_MAX_PER_SOURCE
    schedule_hour: int = DEFAULT_SCHEDULE_HOUR
    schedule_minute: int = DEFAULT_SCHEDULE_MINUTE
    keywords: list[str] = field(default_factory=list)


def load_keywords(db: Session, user_id: str = DEFAULT_USER_ID) -> list[str]:
    """SR-F-101. 순서는 명세에 없으므로 결정적으로 오름차순 고정한다."""
    return list(
        db.scalars(
            select(Keyword.value)
            .where(Keyword.user_id == user_id)
            .order_by(Keyword.value.asc())
        ).all()
    )


def load_settings(db: Session, user_id: str = DEFAULT_USER_ID) -> SettingsData:
    """SR-F-101. 설정 행이 없으면 빈 값과 기본 건수를 돌려준다.

    설정 화면이 빈 양식으로 뜨고 사용자가 채우면 된다.
    """
    row = db.scalar(select(Setting).where(Setting.user_id == user_id))
    keywords = load_keywords(db, user_id)
    if row is None:
        return SettingsData(keywords=keywords)
    return SettingsData(
        mail_subject=row.mail_subject,
        mail_to=row.mail_to,
        max_per_source=row.max_per_source,
        schedule_hour=row.schedule_hour,
        schedule_minute=row.schedule_minute,
        keywords=keywords,
    )


def save_settings(
    db: Session, data: SettingsData, user_id: str = DEFAULT_USER_ID
) -> SettingsData:
    """SR-F-107. 저장 즉시 유효하다. 다음 실행이 이 값을 읽는다.

    키워드는 전체 교체다. 설정 화면이 목록 전체를 보내온다.
    """
    row = db.scalar(select(Setting).where(Setting.user_id == user_id))
    if row is None:
        row = Setting(id=new_ulid(), user_id=user_id)
        db.add(row)

    row.mail_subject = data.mail_subject
    row.mail_to = data.mail_to
    row.max_per_source = data.max_per_source
    row.schedule_hour = data.schedule_hour
    row.schedule_minute = data.schedule_minute

    incoming = set(data.keywords)
    existing = {
        k.value: k
        for k in db.scalars(select(Keyword).where(Keyword.user_id == user_id)).all()
    }

    for value, keyword in existing.items():
        if value not in incoming:
            db.delete(keyword)

    for value in incoming - set(existing):
        db.add(Keyword(id=new_ulid(), value=value, user_id=user_id))

    db.commit()
    return load_settings(db, user_id)
