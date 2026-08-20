import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.events.cooldown import CooldownManager
from app.agents.decision_engine import evaluate_trigger
from datetime import datetime, timezone
import dateutil.parser

logger = logging.getLogger(__name__)

async def process_event(session: AsyncSession, user: User, event_type: str, event_data: dict):
    # Apply rules
    trigger_key = f"{event_type}_{event_data.get('id', 'default')}"
    
    if event_type == "MeetingCreated":
        # Check if meeting is within 24h
        if "start_at" in event_data and event_data["start_at"]:
            try:
                start_dt = dateutil.parser.parse(event_data["start_at"])
                if (start_dt - datetime.now(timezone.utc)).total_seconds() > 86400:
                    return # Too far in the future
            except Exception:
                pass
        
        # Check cooldown (only trigger once per meeting id)
        if not await CooldownManager.can_trigger(session, str(user.id), trigger_key, cooldown_hours=24):
            return
            
    elif event_type == "MorningBriefingTrigger":
        trigger_key = f"MorningBriefing_{datetime.now(timezone.utc).date()}"
        if not await CooldownManager.can_trigger(session, str(user.id), trigger_key, cooldown_hours=12):
            return

    # Route to Decision Engine
    decision = await evaluate_trigger(session, user, event_type, event_data, "User needs proactive monitoring.")
    
    if decision.get("decision") == "ACT":
        logger.info(f"TriggerEngine deciding to ACT on {event_type} with workflow {decision.get('workflow')}")
        from app.agents.workflows.engine import execute_workflow
        await execute_workflow(session, user, decision.get("workflow"), event_data)
        
    elif decision.get("decision") == "NOTIFY":
        logger.info(f"TriggerEngine deciding to NOTIFY on {event_type}")
