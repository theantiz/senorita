from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

# ─── Connection pool tuning ───────────────────────────────────────────────────
# pool_size:     Permanent connections kept alive (matches typical FastAPI worker count)
# max_overflow:  Burst connections above pool_size (short-lived)
# pool_timeout:  Seconds to wait for a connection before raising (avoids silent hangs)
# pool_recycle:  Recycle connections older than N seconds (avoids stale idle connections)
# pool_pre_ping: Verify connectivity on checkout (catches dropped TCP connections)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,    # 30 min – shorter than typical PG idle timeout (1 hour)
    pool_pre_ping=True,   # Detects severed connections before use
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
