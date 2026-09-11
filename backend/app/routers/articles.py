"""기사 조회 (SR-F-602~606, 부록 A.1/A.2)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import kst_day_end_utc, kst_day_start_utc
from app.constants import DEFAULT_USER_ID
from app.db import get_db
from app.models import Article
from app.schemas.article import ArticleOut
from app.schemas.common import ListResponse

# SR-F-602. 부록 A.2의 기본값·상한.
DEFAULT_ITEMS_PER_PAGE = 20
MAX_ITEMS_PER_PAGE = 100

router = APIRouter(tags=["articles"])


@router.get("/articles", response_model=ListResponse[ArticleOut])
def list_articles(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(
        default=DEFAULT_ITEMS_PER_PAGE, ge=1, le=MAX_ITEMS_PER_PAGE
    ),
    keyword: str | None = Query(default=None, description="키워드 완전 일치 (SR-F-603)"),
    site: str | None = Query(default=None, description="피드 소스 표시명 (SR-F-603)"),
    date_from: date | None = Query(
        default=None,
        alias="from",
        description="수집일 시작 (포함). Asia/Seoul 기준 일자 (SR-F-604)",
    ),
    date_to: date | None = Query(
        default=None,
        alias="to",
        description="수집일 종료 (포함). Asia/Seoul 기준 일자 (SR-F-604)",
    ),
) -> ListResponse[ArticleOut]:
    """SR-F-602~606. 조건에 맞는 기사가 없으면 빈 목록과 200을 준다."""
    filters = [Article.user_id == DEFAULT_USER_ID]

    # 빈 문자열은 필터가 아니라 "전체"다. 프론트가 빈 값을 빼고 보내지만
    # 직접 호출하는 쪽도 있으므로 여기서도 막는다.
    if keyword:
        filters.append(Article.keyword == keyword)
    if site:
        filters.append(Article.site == site)

    # 보관은 UTC(SR-D-203)이고 화면은 Asia/Seoul로 표시한다. 사용자가 고른
    # 날짜는 KST 기준이므로 그 날의 KST 00:00~23:59를 UTC 구간으로 바꾼다.
    if date_from:
        filters.append(Article.collected_at >= kst_day_start_utc(date_from))
    if date_to:
        filters.append(Article.collected_at <= kst_day_end_utc(date_to))

    total_count = (
        db.scalar(select(func.count()).select_from(Article).where(*filters)) or 0
    )
    rows = db.scalars(
        select(Article)
        .where(*filters)
        # SR-F-605. id는 ULID라 생성 순서를 따르므로 동률을 결정적으로 가른다.
        .order_by(Article.collected_at.desc(), Article.id.desc())
        .offset((page - 1) * items_per_page)
        .limit(items_per_page)
    ).all()

    return ListResponse[ArticleOut](
        total_count=total_count,
        page=page,
        items_per_page=items_per_page,
        items=[ArticleOut.model_validate(row) for row in rows],
    )
