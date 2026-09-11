from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import register_error_handlers
from app.routers import executions, feed_sources, stubs


def create_app() -> FastAPI:
    app = FastAPI(title="NewsFlow API")

    # SR-I-306 / SR-N-304: 지정된 출처만 허용.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(feed_sources.router)
    app.include_router(executions.router)
    app.include_router(stubs.router)
    return app


app = create_app()
