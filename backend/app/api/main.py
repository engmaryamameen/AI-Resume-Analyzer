from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.admin.router import router as admin_router
from app.api.analyses_router import router as analyses_router
from app.api.auth_router import router as auth_router
from app.api.jobs_router import router as jobs_router
from app.api.resumes_router import router as resumes_router
from app.api.schemas import ErrorResponse
from app.api.system_router import router as system_router
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, NotFound, ServiceUnavailable, install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import BodyLimitMiddleware, RequestContextMiddleware
from app.core.security import constant_time_equal
from app.db.session import get_db
from app.demo.router import router as demo_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on placeholder secrets in production
    app = FastAPI(
        title="Résumé Intelligence API",
        version="0.1.0",
        description="Evidence-based résumé analysis. Errors share one envelope: "
                    "`{error: {code, message, details, request_id}}`.",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
        responses={r: {"model": ErrorResponse} for r in (401, 403, 404, 409, 413, 422, 429)},
    )
    install_error_handlers(app)
    # add_middleware wraps outermost-last: request context is outermost, then CORS, then body limit.
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes + 256 * 1024)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"], max_age=600)
    app.add_middleware(RequestContextMiddleware, settings=settings)

    for r in (auth_router, resumes_router, jobs_router, analyses_router, demo_router, admin_router, system_router):
        app.include_router(r, prefix=API_PREFIX)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz(db: Session = Depends(get_db), s: Settings = Depends(get_settings)) -> dict:
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - readiness must report, not raise details
            raise ServiceUnavailable("Database unavailable.") from exc
        if not s.storage_dir.is_dir():
            raise ServiceUnavailable("Storage unavailable.")
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics(authorization: str | None = Header(default=None), s: Settings = Depends(get_settings)) -> Response:
        if not s.metrics_token:
            raise NotFound("Not found.")
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not supplied or not constant_time_equal(supplied, s.metrics_token):
            raise Forbidden("Invalid metrics token.", code="metrics_forbidden")
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
