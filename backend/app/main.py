"""FastAPI application entrypoint for Señorita backend."""

import hashlib
import secrets
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

import app.integrations.gmail  # Register the Gmail adapter
import app.integrations.slack  # Register the Slack adapter
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logger import logger
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
        # Check specifically for "admin" user
        stmt = select(User).where(User.name == "admin")
        result = await session.execute(stmt)
        admin = result.scalars().first()

        if not admin:
            admin = User(
                name="admin",
                timezone="UTC",
                autonomy_level=5,
                style_profile={}
            )
            session.add(admin)
            await session.flush()

        # Invalidate old admin tokens and generate a fresh one
        await session.execute(
            delete(AuthToken).where(AuthToken.user_id == admin.id)
        )

        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        auth_token = AuthToken(
            user_id=admin.id,
            token_hash=token_hash
        )
        session.add(auth_token)
        await session.commit()

        logger.info("=" * 60)
        logger.info("  ADMIN USER READY")
        logger.info("  Name:  admin")
        logger.info(f"  Token: {raw_token}")
        logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown."""
    # Startup: create tables (in production use Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin user if no users exist
    await seed_admin()

    # Start background workers if not testing
    import os
    if not os.environ.get("TESTING"):
        from app.integrations.gmail_sync import start_gmail_sync_engine
        from app.integrations.google_calendar_sync import start_google_calendar_sync_engine
        from app.workers.monitoring.proactive_engine import start_proactive_engine
        from app.workers.reminders.scheduler import start_scheduler_in_background

        sch = start_scheduler_in_background()
        start_proactive_engine(sch)
        start_gmail_sync_engine(sch)
        start_google_calendar_sync_engine(sch)



    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Señorita API",
    description="Intelligent personal AI assistant backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Database integrity error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Database constraint violation occurred."},
    )

# Register router
app.include_router(api_router, prefix="/api/v1")




if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
