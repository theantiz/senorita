from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.run import AgentRun, AgentEvent
from app.agents.tool_registry import get_tool_registry, get_tool_executor
import json
import logging

logger = logging.getLogger(__name__)

UNDO_MAPPING = {
    "create_task": "delete_task",
    "calendar.create_event": "calendar.delete_event"
}

async def rollback_action(session: AsyncSession, run_id: str, user) -> bool:
    stmt = select(AgentEvent).where(AgentEvent.run_id == run_id, AgentEvent.event_type == "agent.tool_executed")
    res = await session.execute(stmt)
    events = res.scalars().all()
    
    for event in events:
        try:
            payload = event.metadata_payload
            tool_name = payload.get("tool_name")
            if tool_name in UNDO_MAPPING:
                inverse_tool = UNDO_MAPPING[tool_name]
                # Extract created ID
                output = payload.get("output", "{}")
                if isinstance(output, str):
                    output_data = json.loads(output)
                else:
                    output_data = output
                
                # Assume output contains id of the created object
                created_id = output_data.get("id")
                if not created_id:
                    continue
                    
                # Execute inverse
                executor = get_tool_executor()
                await executor.execute_tool(inverse_tool, {"id": created_id}, None) # Requires tool context
        except Exception as e:
            logger.error(f"Undo failed for run {run_id}: {e}")
            return False
            
    return True
