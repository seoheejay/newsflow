"""아직 구현되지 않은 엔드포인트의 빈 응답.

프론트가 목을 떼는 순서(부록 B)에 맞춰 하나씩 실데이터로 교체된다.
지우면 프론트와 docs/README.md가 깨지므로 남겨둔다.
"""

from fastapi import APIRouter

router = APIRouter(tags=["stubs"])


# /settings 는 app/routers/settings.py 로 옮겼다 (SR-F-101~107).


@router.get("/articles")  # TODO(SR-F-601~606): 기사 조회
def get_articles(
    page: int = 1,
    items_per_page: int = 20,
    keyword: str | None = None,  # SR-F-603
    site: str | None = None,  # SR-F-603
) -> dict:
    return {
        "total_count": 0,
        "page": page,
        "items_per_page": items_per_page,
        "items": [],
    }


# /collect 와 /executions 는 app/routers/executions.py 로 옮겼다 (SR-F-701~707).
