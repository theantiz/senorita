from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import ActionLog, User
from app.schemas.action_log import ActionLogRead

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=List[ActionLogRead])
async def list_activity(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(ActionLog).where(ActionLog.user_id == current_user.id).order_by(ActionLog.created_at.desc()).limit(50)
    result = await session.execute(stmt)
    return list(result.scalars().all())
