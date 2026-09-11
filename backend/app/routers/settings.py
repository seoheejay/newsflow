"""설정 조회·변경 (SR-F-101~107, 부록 A.1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.db import get_db
from app.errors import ErrorResponse
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.services.settings_store import SettingsData, load_settings, save_settings

router = APIRouter(
    tags=["settings"],
    responses={400: {"model": ErrorResponse}},
)


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsData:
    """SR-F-101."""
    return load_settings(db, DEFAULT_USER_ID)


@router.put("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate, db: Session = Depends(get_db)
) -> SettingsData:
    """SR-F-107. 저장 즉시 유효하고 다음 실행부터 반영된다."""
    return save_settings(
        db,
        SettingsData(
            mail_subject=payload.mail_subject,
            mail_to=str(payload.mail_to),
            max_per_source=payload.max_per_source,
            schedule_hour=payload.schedule_hour,
            schedule_minute=payload.schedule_minute,
            keywords=payload.keywords,
        ),
        DEFAULT_USER_ID,
    )
