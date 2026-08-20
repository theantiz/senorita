import json
import logging
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.agents.gemini_client import get_client

logger = logging.getLogger(__name__)

async def evaluate_trigger(session: AsyncSession, user: User, event_type: str, event_data: dict, context_summary: str) -> Dict[str, Any]:
    """
    Decides whether an autonomous trigger should proceed, notify the user, or do nothing.
    """
    prompt = f"""
You are the Decision Engine for Señorita AI. 
An autonomous event has just occurred. You must decide the appropriate action based on the user's context.

Event Type: {event_type}
Event Data: {json.dumps(event_data)}
User Context: {context_summary}

Analyze the event and output a JSON decision object:
{{
    "is_useful": boolean,
    "is_urgent": boolean,
    "should_notify": boolean,
    "should_act": boolean,
    "should_ask": boolean,
    "reasoning": "string"
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
            "is_useful": False,
            "is_urgent": False,
            "should_notify": False,
            "should_act": False,
            "should_ask": False,
            "reasoning": "Error evaluating decision."
        }
