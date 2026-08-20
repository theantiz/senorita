from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.productivity import FocusSession

class AttentionManager:
    @staticmethod
    async def should_notify(session: AsyncSession, user_id: str, urgency: str) -> bool:
        """Returns True if the notification should go through, False if it should be suppressed."""
        stmt = select(FocusSession).where(FocusSession.user_id == user_id, FocusSession.status == "ACTIVE")
        res = await session.execute(stmt)
        active_session = res.scalars().first()
        
        if active_session:
            if urgency == "CRITICAL":
                return True
            active_session.interruptions_prevented += 1
            await session.commit()
            return False
            
        return True
