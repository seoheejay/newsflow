"""공통 오류 응답 (SR-I-305, SRS 부록 C.2).

응답 형태는 { code, message, fields? }. FastAPI 기본값인 422 + {"detail": ...}를 덮어쓴다.
이후 모든 엔드포인트가 이 모듈을 재사용한다.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "입력값을 확인해주세요"


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "서버 오류가 발생했습니다"

    def __init__(
        self, message: str | None = None, fields: list[str] | None = None
    ) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.fields = fields


class ValidationAppError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"
    message = VALIDATION_MESSAGE


class FeedUrlInvalidError(AppError):
    """SR-F-202. VALIDATION_ERROR와 별개 코드를 요구하므로 별도 예외로 둔다."""

    status_code = 400
    code = "FEED_URL_INVALID"
    message = "주소 템플릿은 http:// 또는 https:// 로 시작해야 합니다"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "대상을 찾을 수 없습니다"


class DuplicateNameError(AppError):
    """SR-F-206."""

    status_code = 409
    code = "DUPLICATE_NAME"
    message = "이미 사용 중인 표시명입니다"


class EmailSendFailedError(AppError):
    """SR-F-508."""

    status_code = 500
    code = "EMAIL_SEND_FAILED"
    message = "메일 발송에 실패했습니다"


class ExecutionInProgressError(AppError):
    """SR-F-705. 아직 사용처는 없지만 코드 표(부록 C.2)를 한자리에 모아둔다."""

    status_code = 409
    code = "EXECUTION_IN_PROGRESS"
    message = "진행 중인 실행이 있습니다"


class ErrorResponse(BaseModel):
    """OpenAPI 문서용 스키마."""

    code: str
    message: str
    fields: list[str] | None = None


_STATUS_TO_CODE = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def _payload(code: str, message: str, fields: list[str] | None = None) -> dict:
    body: dict = {"code": code, "message": message}
    # SR-I-305는 "입력값 오류 시 fields를 추가"라고 했다. 그 외에는 키 자체를 넣지 않는다.
    if fields:
        body["fields"] = fields
    return body


def _fields_from_validation_error(exc: RequestValidationError) -> list[str]:
    """loc에서 body/query/path 접두어를 떼고 순서를 유지하며 중복을 제거한다."""
    fields: list[str] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        if loc and loc[0] in ("body", "query", "path", "header", "cookie"):
            loc = loc[1:]
        name = ".".join(loc)
        if name and name not in fields:
            fields.append(name)
    return fields


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.fields),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI 기본은 422다. 부록 C.2와 docs/README.md는 400을 요구한다.
        return JSONResponse(
            status_code=400,
            content=_payload(
                "VALIDATION_ERROR",
                VALIDATION_MESSAGE,
                _fields_from_validation_error(exc),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Starlette 쪽을 잡아야 라우터가 만드는 404/405까지 같은 형태로 나간다.
        code = _STATUS_TO_CODE.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # SR-N-204: 예외가 나도 시스템은 계속 산다. 스택 트레이스는 응답에 싣지 않는다.
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_payload(AppError.code, AppError.message),
        )
