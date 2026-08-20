"""Implicit memory capture — automatically extracts key info from conversations (T4.2)."""

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import settings


async def capture_implicit_memories():
    """Analyze recent conversations and extract memorable facts."""
    try:
        from app.db.session import async_session_factory
        from sqlalchemy import select
        from app.db.models.conversation import Conversation
        from app.agents.gemini_client import get_client, start_chat
        from app.agents.tool_registry import _handle_store_memory
        import json

        async with async_session_factory() as session:
            # Get distinct users with conversations in the last hour
            an_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            stmt = select(Conversation.user_id).where(Conversation.created_at >= an_hour_ago).distinct()
            res = await session.execute(stmt)
            users = res.scalars().all()

            for user_id in users:
                # Fetch their recent conversation
                c_stmt = select(Conversation).where(Conversation.user_id == user_id, Conversation.created_at >= an_hour_ago).order_by(Conversation.created_at)
                c_res = await session.execute(c_stmt)
                convs = c_res.scalars().all()
                if not convs:
                    continue

                transcript = "\n".join([f"{c.role}: {c.content}" for c in convs])
                prompt = f"""
Analyze the following conversation transcript and extract any long-term memorable facts, preferences, or relationships about the user.
Return ONLY a JSON list of objects, each with:
- "content": string (the fact)
- "memory_type": string (one of: person, preference, date, promise, context)
- "confidence": string (HIGH, MEDIUM, LOW)
- "importance": float (0.0 to 1.0)

Transcript:
{transcript}
"""
                chat = start_chat()
                response = await chat.send_message(prompt)
                text = (response.text or "").strip()
                if text.startswith("```json"): text = text[7:-3]
                elif text.startswith("```"): text = text[3:-3]
                
                try:
                    facts = json.loads(text)
                    for f in facts:
                        await _handle_store_memory(
                            session=session,
                            user_id=user_id,
                            content=f.get("content", ""),
                            memory_type=f.get("memory_type", "context"),
                            confidence=f.get("confidence", "MEDIUM"),
                            importance_score=f.get("importance", 0.5)
                        )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Failed to parse or store implicit memory: {e}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Implicit memory capture failed: {e}")


async def run_implicit_capture():
    """Background loop for implicit memory extraction."""
    while True:
        await capture_implicit_memories()
        await asyncio.sleep(3600)  # Once per hour


def start_implicit_capture():
    """Start implicit memory capture in background."""
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(run_implicit_capture())

