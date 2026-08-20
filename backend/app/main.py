"""FastAPI application entrypoint for Señorita backend."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError

import app.integrations.gmail  # Register the Gmail adapter
import app.integrations.slack  # Register the Slack adapter
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logger import logger
from app.core.metrics import get_metrics_response, websocket_active_connections
from app.core.security import generate_token, hash_token
from app.db.base import Base
from app.db.models import *  # noqa: F401, F403 — ensure all models are registered
from app.db.session import AsyncSession, engine


async def seed_admin():
    """Ensure an admin user always exists. Creates one if missing."""
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import AuthToken, User

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        stmt = select(User).where(User.name == "admin")
        result = await session.execute(stmt)
        admin = result.scalars().first()

        if not admin:
            admin = User(
                name="admin",
                timezone="UTC",
                autonomy_level="FULL_AUTO",
                style_profile={},
            )
            session.add(admin)
            await session.flush()

        await session.execute(delete(AuthToken).where(AuthToken.user_id == admin.id))

        raw_token = generate_token()
        auth_token = AuthToken(user_id=admin.id, token_hash=hash_token(raw_token))
        session.add(auth_token)
        await session.commit()

        logger.info("=== ADMIN USER READY  Token: " + raw_token + " ===")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown."""
    if settings.TESTING:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    await seed_admin()

    if not settings.TESTING:
        import asyncio

        from app.integrations.gmail_sync import start_gmail_sync_engine
        from app.integrations.google_calendar_sync import start_google_calendar_sync_engine
        from app.workers.monitoring.proactive_engine import start_proactive_engine
        from app.workers.memory_capture.behavior_learning import start_behavior_learning_engine
        from app.workers.reminders.scheduler import start_scheduler_in_background
        from app.workers.stale_run_recovery import stale_run_recovery_loop

        scheduler = start_scheduler_in_background()
        start_proactive_engine(scheduler)
        start_behavior_learning_engine(scheduler)
        start_gmail_sync_engine(scheduler)
        start_google_calendar_sync_engine(scheduler)

        # Stale run recovery runs as a lightweight background coroutine
        asyncio.create_task(stale_run_recovery_loop())

        # start_morning_briefing_cron(scheduler)
    yield

    await engine.dispose()


app = FastAPI(
    title="Señorita API",
    description="Intelligent personal AI assistant backend",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # HSTS only in production (not dev)
    if not settings.TESTING and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^http://(?:localhost|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error("db.integrity_error", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Database constraint violation occurred."},
    )


# ─── Prometheus metrics endpoint ───────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    """Prometheus scrape target. Secure behind a network firewall in production."""
    data, content_type = get_metrics_response()
    return Response(content=data, media_type=content_type)


# ─── Liveness / readiness probes ──────────────────────────────────────────────
@app.get("/health/live", tags=["Health"], include_in_schema=False)
async def liveness():
    """Liveness: only confirms the process is responsive."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"], include_in_schema=False)
async def readiness():
    """Readiness: verifies Postgres is reachable before accepting traffic."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.error("health.ready.db_unavailable", error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unreachable"},
        )


app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
