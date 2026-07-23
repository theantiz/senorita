from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from db.session import get_db
from db.models import User, ActionLog
from schemas.action_log import ActionLogRead
from core.security import get_current_user

router = APIRouter(prefix="/activity", tags=["activity"])

@router.get("", response_model=List[ActionLogRead])
async def list_activity(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(ActionLog).where(ActionLog.user_id == current_user.id).order_by(ActionLog.created_at.desc()).limit(50)
    result = await session.execute(stmt)
    return list(result.scalars().all())
