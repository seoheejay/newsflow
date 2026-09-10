"""피드 소스 CRUD (SR-F-201~209, 부록 A.1/A.3)."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.db import get_db
from app.errors import DuplicateNameError, ErrorResponse, NotFoundError
from app.ids import new_ulid
from app.models import FeedSource
from app.schemas.common import ListResponse
from app.schemas.feed_source import FeedSourceCreate, FeedSourceOut, FeedSourceUpdate
from app.services.url_template import validate_url_template

# ASM-04가 피드 소스를 20개 이하로 한정하므로 기본값을 상한과 같이 둔다.
# 기본 20이면 상한과 겹쳐 경계에서 조용히 잘린다.
DEFAULT_ITEMS_PER_PAGE = 100
MAX_ITEMS_PER_PAGE = 100

router = APIRouter(
    prefix="/feed-sources",
    tags=["feed-sources"],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)


def _is_duplicate_name(exc: IntegrityError) -> bool:
    """MySQL과 SQLite의 유일 제약 위반 메시지를 함께 판정한다.

    무관한 무결성 오류가 409로 둔갑하지 않도록 좁혀서 본다.
    """
    msg = str(exc.orig)
    return (
        "uq_feed_sources_name" in msg
        or "feed_sources.name" in msg
        or "1062" in msg
    )


def _commit_or_duplicate(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_duplicate_name(exc):
            # SR-F-206. 선검사가 아니라 DB 제약에 맡긴다 — 동시 요청에서 선검사는 TOCTOU다.
            raise DuplicateNameError(fields=["name"]) from exc
        raise


def _get_or_404(db: Session, feed_source_id: str) -> FeedSource:
    feed_source = db.get(FeedSource, feed_source_id)
    if feed_source is None:
        raise NotFoundError("피드 소스를 찾을 수 없습니다")
    return feed_source


@router.get("", response_model=ListResponse[FeedSourceOut])
def list_feed_sources(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(
        default=DEFAULT_ITEMS_PER_PAGE, ge=1, le=MAX_ITEMS_PER_PAGE
    ),
) -> ListResponse[FeedSourceOut]:
    total_count = db.scalar(select(func.count()).select_from(FeedSource)) or 0
    rows = db.scalars(
        select(FeedSource)
        # SR-F-209: 정렬 순서 오름차순, 동일 값은 표시명 오름차순.
        .order_by(FeedSource.sort_order.asc(), FeedSource.name.asc())
        .offset((page - 1) * items_per_page)
        .limit(items_per_page)
    ).all()
    return ListResponse[FeedSourceOut](
        total_count=total_count,
        page=page,
        items_per_page=items_per_page,
        items=[FeedSourceOut.model_validate(row) for row in rows],
    )


@router.post(
    "",
    response_model=FeedSourceOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
def create_feed_source(
    payload: FeedSourceCreate, db: Session = Depends(get_db)
) -> FeedSource:
    validate_url_template(payload.url_template)  # SR-F-202
    feed_source = FeedSource(
        id=new_ulid(),
        user_id=DEFAULT_USER_ID,
        **payload.model_dump(),
    )
    db.add(feed_source)
    _commit_or_duplicate(db)
    db.refresh(feed_source)
    return feed_source


@router.put(
    "/{feed_source_id}",
    response_model=FeedSourceOut,
    responses={409: {"model": ErrorResponse}},
)
def update_feed_source(
    feed_source_id: str, payload: FeedSourceUpdate, db: Session = Depends(get_db)
) -> FeedSource:
    feed_source = _get_or_404(db, feed_source_id)
    validate_url_template(payload.url_template)  # SR-F-202
    for field, value in payload.model_dump().items():
        setattr(feed_source, field, value)
    _commit_or_duplicate(db)
    db.refresh(feed_source)
    return feed_source


@router.delete("/{feed_source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed_source(feed_source_id: str, db: Session = Depends(get_db)) -> Response:
    feed_source = _get_or_404(db, feed_source_id)
    # SR-F-208: Article.site는 표시명 스냅샷이고 FK가 없으므로 기사는 그대로 남는다.
    db.delete(feed_source)
    db.commit()
    # 204에는 본문이 없어야 한다. 프론트가 res.json()을 부르면 깨진다.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
