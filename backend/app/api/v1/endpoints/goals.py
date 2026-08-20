from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.models.goal import Goal, Project

router = APIRouter()

class GoalCreate(BaseModel):
    name: str
    description: Optional[str] = None
    deadline: Optional[str] = None

@router.get("", response_model=Any)
async def list_goals(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(Goal).where(Goal.user_id == current_user.id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=Any)
async def create_goal(goal: GoalCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.memory.embeddings import embed_text
    import dateutil.parser
    
    g = Goal(
        user_id=current_user.id,
        name=goal.name,
        description=goal.description,
        deadline=dateutil.parser.parse(goal.deadline) if goal.deadline else None,
        embedding=await embed_text(f"{goal.name} {goal.description or ''}", task_type="RETRIEVAL_DOCUMENT")
    )
    db.add(g)
    await db.commit()
    return g
