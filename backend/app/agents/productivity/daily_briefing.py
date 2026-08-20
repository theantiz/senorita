from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User
from app.db.models.goal import Goal
from app.db.models.task import Task

async def generate_daily_briefing(session: AsyncSession, user: User) -> dict:
    # 1. Top Goal
    stmt_g = select(Goal).where(Goal.user_id == user.id, Goal.status == "ACTIVE").limit(1)
    res_g = await session.execute(stmt_g)
    goal = res_g.scalars().first()
    
    # 2. Tasks
    stmt_t = select(Task).where(Task.user_id == user.id, Task.status != "COMPLETED").limit(3)
    res_t = await session.execute(stmt_t)
    tasks = res_t.scalars().all()
    
    return {
        "top_goal": goal.name if goal else "No active goals",
        "priorities": [t.title for t in tasks],
        "needs_attention": len(tasks),
        "recommendation": "Focus on high-priority tasks in the morning."
    }
