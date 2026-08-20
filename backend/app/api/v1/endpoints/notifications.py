from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import NotificationLog, User

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
