from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.cooldown import Cooldown
from app.db.models.user import User

class CooldownManager:
    @staticmethod
    async def can_trigger(session: AsyncSession, user_id: str, trigger_key: str, cooldown_hours: int = 12) -> bool:
        stmt = select(Cooldown).where(
            Cooldown.user_id == user_id,
            Cooldown.trigger_key == trigger_key
        )
        res = await session.execute(stmt)
        record = res.scalars().first()
        now = datetime.now(timezone.utc)
        
        if record:
            if now < record.cooldown_until:
                return False
            else:
                record.last_executed_at = now
                record.cooldown_until = now + timedelta(hours=cooldown_hours)
                return True
        else:
            new_record = Cooldown(
                user_id=user_id,
                trigger_key=trigger_key,
                last_executed_at=now,
                cooldown_until=now + timedelta(hours=cooldown_hours)
            )
            session.add(new_record)
            return True
