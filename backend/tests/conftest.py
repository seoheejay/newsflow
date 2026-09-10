import os

# app.db가 임포트 시점에 create_engine(settings.database_url)을 부르고
# database_url에는 기본값이 없다. 반드시 app 임포트보다 먼저 심어야 한다.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models as _models  # noqa: F401,E402 - Base.metadata를 채운다
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# 주의: `import app.models`로 쓰면 이름 app이 패키지 모듈로 재바인딩되어
# 위의 FastAPI 인스턴스를 가린다. `from app import models` 형태를 유지할 것.

# StaticPool: 커넥션이 여러 개여도 같은 in-memory DB를 보게 한다.
test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session() -> Session:
    # 라우터가 commit()을 호출하므로 롤백 기반 격리를 쓸 수 없다. 매번 만들고 지운다.
    Base.metadata.create_all(test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)


@pytest.fixture
def client(db_session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def make_payload(**overrides) -> dict:
    payload = {
        "name": "구글",
        "url_template": "https://news.google.com/rss/search?q={keyword}&hl=ko",
        "sort_order": 1,
        "is_active": True,
    }
    payload.update(overrides)
    return payload
