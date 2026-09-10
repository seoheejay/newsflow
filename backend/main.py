"""진입점 시임.

docs/README.md의 `poetry run uvicorn main:app --reload`가 이 파일에 의존한다. 지우지 말 것.
실제 구성은 app/main.py에 있다.
"""

from app.main import app

__all__ = ["app"]
