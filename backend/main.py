"""FastAPI application entrypoint for Señorita backend."""

import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.base import Base
from db.session import engine
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown."""
    # Startup: create tables (in production use Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

