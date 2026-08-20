from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User

async def find_free_block(session: AsyncSession, user: User, duration_minutes: int) -> dict:
    # Deterministic mock for time blocking
    now = datetime.now(timezone.utc)
    return {
        "start": (now + timedelta(hours=1)).isoformat(),
        "end": (now + timedelta(hours=1, minutes=duration_minutes)).isoformat()
    }
