"""아직 구현되지 않은 엔드포인트의 빈 응답.

프론트가 목을 떼는 순서(부록 B)에 맞춰 하나씩 실데이터로 교체된다.
지우면 프론트와 docs/README.md가 깨지므로 남겨둔다.
"""

from fastapi import APIRouter

router = APIRouter(tags=["stubs"])


@router.get("/settings")  # TODO(SR-F-101): 설정 조회
def get_settings() -> dict:
    return {
        "mail_subject": "",
        "mail_to": "",
        "max_per_source": 10,
        "keywords": [],
    }


@router.get("/articles")  # TODO(SR-F-601~606): 기사 조회
def get_articles(page: int = 1, items_per_page: int = 20) -> dict:
    return {
        "total_count": 0,
        "page": page,
        "items_per_page": items_per_page,
        "items": [],
    }


@router.post("/collect", status_code=202)  # TODO(SR-F-701): 수집 실행 요청
def collect() -> dict:
    return {"execution_id": "dummy", "status": "queued"}


@router.get("/executions/{execution_id}")  # TODO(SR-F-706): 실행 상태 조회
def get_execution(execution_id: str) -> dict:
    return {
        "id": execution_id,
        "status": "success",
        "started_at": None,
        "finished_at": None,
        "collected_count": 0,
        "new_count": 0,
        "error": None,
    }
