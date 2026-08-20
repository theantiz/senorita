import json
import logging
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.agents.gemini_client import get_client

logger = logging.getLogger(__name__)

async def evaluate_trigger(session: AsyncSession, user: User, event_type: str, event_data: dict, context_summary: str) -> Dict[str, Any]:
    prompt = f"""
You are the Decision Engine for Señorita AI. 
An autonomous event has just occurred. You must decide the appropriate action based on the user's context.

Event Type: {event_type}
Event Data: {json.dumps(event_data)}
User Context: {context_summary}

Analyze the event and output a JSON decision object EXACTLY matching this format:
{{
    "decision": "ACT" | "NOTIFY" | "IGNORE",
    "confidence": 0.0 to 1.0,
    "reason": "string explaining reasoning",
    "workflow": "prepare_for_meeting" | "daily_planning" | "follow_up_email" | null,
    "urgency": "low" | "medium" | "high"
}}
"""
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
    except Exception as e:
        logger.error(f"Decision engine failure: {e}")
        return {
            "decision": "IGNORE",
            "confidence": 0.0,
            "reason": f"Error evaluating decision: {e}",
            "workflow": None,
            "urgency": "low"
        }
