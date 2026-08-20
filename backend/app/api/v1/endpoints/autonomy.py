from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.models.autonomy_policy import AutonomyPolicy

router = APIRouter()

class AutonomySet(BaseModel):
    action_scope: str
    autonomy_level: str

@router.get("", response_model=Any)
async def list_autonomy(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(AutonomyPolicy).where(AutonomyPolicy.user_id == current_user.id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=Any)
async def set_autonomy(policy: AutonomySet, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(AutonomyPolicy).where(
        AutonomyPolicy.user_id == current_user.id,
        AutonomyPolicy.action_scope == policy.action_scope
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    
    if existing:
        existing.autonomy_level = policy.autonomy_level
    else:
        new_pol = AutonomyPolicy(
            user_id=current_user.id,
            action_scope=policy.action_scope,
            autonomy_level=policy.autonomy_level
        )
        db.add(new_pol)
        
    await db.commit()
    return {"status": "ok"}
