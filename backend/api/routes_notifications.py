from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict, Any

from db.session import get_db
from db.models import User, NotificationLog
from core.security import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_notifications(
    limit: int = 10,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch the most recent proactive notifications dispatched to the user.
    """
    stmt = (
        select(NotificationLog)
        .where(NotificationLog.user_id == user.id)
        .order_by(desc(NotificationLog.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()
    
    return [
        {
            "id": str(log.id),
            "trigger_type": log.trigger_type,
            "message": log.message,
            "importance_score": log.importance_score,
            "dispatched": log.dispatched,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
