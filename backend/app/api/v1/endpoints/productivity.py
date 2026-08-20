from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.models.productivity import FocusSession
from app.agents.productivity.next_action import get_next_best_action
from app.agents.productivity.daily_briefing import generate_daily_briefing
from pydantic import BaseModel
import uuid

router = APIRouter()

@router.get("/next-action")
async def next_action(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_next_best_action(db, current_user)
    
@router.get("/daily-briefing")
async def daily_briefing(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await generate_daily_briefing(db, current_user)

class FocusStart(BaseModel):
    duration_minutes: int
    task_id: str | None = None

@router.post("/focus/start")
async def start_focus(payload: FocusStart, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    fs = FocusSession(
        user_id=current_user.id,
        duration_minutes=payload.duration_minutes,
        task_id=payload.task_id
    )
    db.add(fs)
    await db.commit()
    return {"status": "ACTIVE", "id": fs.id}
    
@router.post("/focus/stop")
async def stop_focus(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(FocusSession).where(FocusSession.user_id == current_user.id, FocusSession.status == "ACTIVE")
    res = await db.execute(stmt)
    fs = res.scalars().first()
    if fs:
        fs.status = "COMPLETED"
        fs.completed_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "COMPLETED"}
    
@router.get("/focus/status")
async def get_focus_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(FocusSession).where(FocusSession.user_id == current_user.id, FocusSession.status == "ACTIVE")
    res = await db.execute(stmt)
    fs = res.scalars().first()
    if fs:
        return {"active": True, "id": fs.id, "duration": fs.duration_minutes, "prevented": fs.interruptions_prevented}
    return {"active": False}
