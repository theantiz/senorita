"""FastAPI application entrypoint for Señorita backend."""

import sys
import secrets
import hashlib
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.base import Base
from db.session import engine, AsyncSession
from db.models import *  # noqa: F401, F403 — ensure all models are registered
from api.routes_health import router as health_router
from api.routes_auth import router as auth_router
from api.routes_contacts import router as contacts_router
from api.routes_tasks import router as tasks_router
from api.routes_reminders import router as reminders_router
from api.routes_calendar import router as calendar_router
from api.routes_memory import router as memory_router
from api.routes_activity import router as activity_router
from api.routes_chat import router as chat_router
from api.routes_system import router as system_router


async def seed_admin():
    """Ensure an admin user always exists. Creates one if missing."""
    from sqlalchemy import select, delete
    from db.models import User, AuthToken
    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
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

        print("=" * 60)
        print("  ADMIN USER READY")
        print("  Name:  admin")
        print(f"  Token: {raw_token}")
        print("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown."""
    # Startup: create tables (in production use Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin user if no users exist
    await seed_admin()

    # Start background workers
    from workers.reminders.scheduler import start_scheduler_in_background
    from workers.monitoring.proactive_engine import start_proactive_engine

    sch = start_scheduler_in_background()
    start_proactive_engine(sch)

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

# Register routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(contacts_router)
app.include_router(tasks_router)
app.include_router(reminders_router)
app.include_router(calendar_router)
app.include_router(memory_router)
app.include_router(activity_router)
app.include_router(chat_router)
app.include_router(system_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )

