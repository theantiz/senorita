from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User
from app.db.models.task import Task
from app.db.models.goal import Goal
from app.agents.gemini_client import get_client
import json

async def get_next_best_action(session: AsyncSession, user: User) -> dict:
    # 1. Fetch pending tasks
    stmt = select(Task).where(Task.user_id == user.id, Task.status != "COMPLETED").limit(10)
    res = await session.execute(stmt)
    tasks = res.scalars().all()
    
    if not tasks:
        return {"action": "relax", "reason": "You have no pending tasks.", "estimated_minutes": 0, "priority": 0.0, "confidence": 1.0}
        
    # 2. Fetch goals
    stmt_g = select(Goal).where(Goal.user_id == user.id, Goal.status == "ACTIVE").limit(5)
    res_g = await session.execute(stmt_g)
    goals = res_g.scalars().all()
    
    # 3. LLM synthesizes next action
    prompt = f"Given these tasks: {[t.title for t in tasks]} and goals: {[g.name for g in goals]}, output a JSON object indicating the next best action matching this format: {{\"action\": \"task name\", \"reason\": \"string\", \"estimated_minutes\": 30, \"priority\": 0.9, \"confidence\": 0.95}}"
    
    client = get_client()
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[prompt]
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text)
    except Exception:
        return {"action": tasks[0].title, "reason": "Highest in queue.", "estimated_minutes": 30, "priority": 0.8, "confidence": 0.5}

