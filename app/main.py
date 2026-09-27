import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.centres import router as centres_router
from app.api.v1.diagnostic_tests import router as tests_router
from app.api.v1.payments import router as payments_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.session import Base, engine

configure_logging(settings.ENVIRONMENT)
log = get_logger("eve")

# Import models so Base.metadata includes every table before create_all.
import app.models  # noqa: F401,E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("startup", db_configured=bool(settings.DATABASE_URL), env=settings.ENVIRONMENT)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "EVE Healthcare — diagnostic test bookings with simulated payments. "
            "Interactive docs: /docs (Swagger) and /redoc."
        ),
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.CORS_ORIGINS == "*" else settings.CORS_ORIGINS.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logger(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):  # noqa: BLE001 - top-level guard
        log.error("unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/", tags=["meta"])
    def root():
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(centres_router, prefix="/api/v1")
    app.include_router(tests_router, prefix="/api/v1")
    app.include_router(bookings_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")

    return app


app = create_app()
