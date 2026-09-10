# NewsFlow

키워드 기반 뉴스 스크랩 자동화. RSS 수집 → 중복 제거 → 메일 발송.

## 문서
- `docs/newsflow-srs-v10.docx` — 요구사항. SR-F-xxx ID로 참조
- SRS 부록 A에 API 계약, 부록 B에 처리 흐름

## 구조
- `backend/` FastAPI + SQLAlchemy + Celery, Poetry 관리
- `frontend/` React + Vite

## 규칙
- JSON 속성명 snake_case
- 일시는 ISO 8601 UTC
- 목록 응답: { total_count, page, items_per_page, items }
- 오류 응답: { code, message, fields? }
- 커밋 메시지에 SR ID 포함: `feat(SR-F-405): ...`
- 테스트 함수명에 SR ID 포함

## 환경
- Windows / PowerShell
- Python 3.13 (3.14 아님)
- 백엔드 8000, 프론트 5173
- MySQL은 docker-compose, 포트 3307
- Celery 워커는 `--pool=solo` 필요

## 주의
- `poetry add`로만 패키지 추가 (pip 금지)
- 새 패키지 디렉터리마다 `__init__.py` 필수
- Alembic 리비전 생성 후 파일 내용 확인할 것