from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.models.run import AgentRun
from app.db.models.feedback import DecisionFeedback
from app.db.models.autonomy_policy import AutonomyPolicy
from pydantic import BaseModel
import uuid

router = APIRouter()

class FeedbackCreate(BaseModel):
    run_id: str
    feedback_type: str

@router.post("/")
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(AgentRun).where(AgentRun.id == uuid.UUID(payload.run_id), AgentRun.user_id == current_user.id)
    res = await db.execute(stmt)
    run = res.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    feedback = DecisionFeedback(
        user_id=current_user.id,
        run_id=run.id,
        workflow_id=run.workflow_id,
        feedback_type=payload.feedback_type
    )
    db.add(feedback)
    
    # Simple learning execution immediately
    if payload.feedback_type == "NEVER_DO_THIS" and run.workflow_id:
        # Lower autonomy policy
        stmt_policy = select(AutonomyPolicy).where(AutonomyPolicy.user_id == current_user.id, AutonomyPolicy.action_scope == run.workflow_id)
        res_policy = await db.execute(stmt_policy)
        policy = res_policy.scalars().first()
        if policy:
            policy.autonomy_level = "SUGGEST"
        else:
            db.add(AutonomyPolicy(user_id=current_user.id, action_scope=run.workflow_id, autonomy_level="SUGGEST"))
            
    await db.commit()
    return {"status": "ok"}
