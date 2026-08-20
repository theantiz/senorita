from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.executor import PlanExecutor
from app.api.deps import get_current_user
from app.db.models import User
from app.db.models.plan import AgentPlan
from app.db.session import get_db

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resume a run that is paused or waiting for confirmation.
    """
    from app.db.models.run import AgentRun

    stmt = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ("PAUSED", "WAITING_FOR_CONFIRMATION"):
        raise HTTPException(status_code=400, detail=f"Cannot resume run in status {run.status}")

    run.status = "RUNNING"
    await db.commit()

    import asyncio

    from app.agents.llm_provider import GeminiProvider
    from app.db.session import async_session_factory

    async def _bg_resume_executor(r_id):
        try:
            async with async_session_factory() as bg_session:
                executor = PlanExecutor(bg_session, r_id, GeminiProvider())
                await executor.run()
        except Exception:
            pass

    asyncio.create_task(_bg_resume_executor(run.id))

    return {"message": "Run resumed", "run_id": run_id}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel an active run.
    """
    from app.db.models.run import AgentRun

    stmt = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in ("COMPLETED", "FAILED", "CANCELLED", "EXPIRED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run already in terminal state {run.status}")

    run.status = "CANCELLED"
    await db.commit()

    return {"message": "Run cancelled", "run_id": run_id}


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload

    from app.db.models.run import AgentRun

    stmt = (
        select(AgentRun)
        .options(selectinload(AgentRun.plan).selectinload(AgentPlan.steps))
        .where(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    payload = {
        "agent_run_id": str(run.id),
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "plan_id": str(run.plan_id) if run.plan_id else None,
    }

    if run.plan:
        payload["plan"] = {
            "status": run.plan.status,
            "goal": run.plan.goal,
            "steps": [
                {"step_id": s.step_id, "tool_name": s.tool_name, "status": s.status, "depends_on": s.depends_on}
                for s in run.plan.steps
            ],
        }

    return payload
