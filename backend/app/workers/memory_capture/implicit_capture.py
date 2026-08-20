"""Implicit memory capture — automatically extracts key info from conversations (T4.2)."""

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import settings


async def capture_implicit_memories():
    """Analyze recent conversations and extract memorable facts."""
    try:
        import json

        from sqlalchemy import select

        from app.agents.gemini_client import get_client, start_chat
        from app.agents.tool_registry import _handle_store_memory
        from app.db.models.conversation import Conversation
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            # Get distinct users with conversations in the last hour
            an_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            stmt = select(Conversation.user_id).where(Conversation.created_at >= an_hour_ago).distinct()
            res = await session.execute(stmt)
            users = res.scalars().all()

            for user_id in users:
                # Fetch their recent conversation
                c_stmt = (
                    select(Conversation)
                    .where(Conversation.user_id == user_id, Conversation.created_at >= an_hour_ago)
                    .order_by(Conversation.created_at)
                )
                c_res = await session.execute(c_stmt)
                convs = c_res.scalars().all()
                if not convs:
                    continue

                transcript = "\n".join([f"{c.role}: {c.content}" for c in convs])
                prompt = f"""
Analyze the following conversation transcript and extract any long-term memorable facts, preferences, or relationships about the user.
CRITICAL: Only extract facts that have long-term usefulness. DO NOT extract short-term tasks, greetings ("hello", "thanks"), temporary contexts ("okay", "do this"), or trivial details.

Return a JSON object with two arrays: "memories" and "preferences".

For "memories" (facts, dates, people, contexts):
- "content": string (the extracted fact)
- "memory_type": string (person, date, promise, context)
- "confidence": string (HIGH, MEDIUM, LOW)
- "importance": float (0.0 to 1.0)
- "valid_from": string (ISO8601 date, or null if perpetual)
- "valid_until": string (ISO8601 date, or null if perpetual)

For "preferences" (behavioral patterns, style, rules):
- "domain": string (e.g., 'communication', 'scheduling', 'coding')
- "preference": string (e.g., 'prefers concise emails', 'likes Java examples')
- "confidence": string (HIGH, MEDIUM, LOW)
- "strength": float (0.0 to 1.0)

If there are no useful facts, return empty arrays.

Transcript:
{transcript}
"""
                chat = start_chat()
                response = await chat.send_message(prompt)
                text = (response.text or "").strip()
                if text.startswith("```json"):
                    text = text[7:-3]
                elif text.startswith("```"):
                    text = text[3:-3]

                try:
                    from dateutil.parser import parse as parse_date

                    from app.db.models.preference import Preference

                    data = json.loads(text)

                    for m in data.get("memories", []):
                        valid_from_str = m.get("valid_from")
                        valid_until_str = m.get("valid_until")
                        vf = parse_date(valid_from_str) if valid_from_str else None
                        vu = parse_date(valid_until_str) if valid_until_str else None

                        await _handle_store_memory(
                            session=session,
                            user_id=user_id,
                            content=m.get("content", ""),
                            memory_type=m.get("memory_type", "context"),
                            confidence=m.get("confidence", "MEDIUM"),
                            importance_score=m.get("importance", 0.5),
                            valid_from=vf,
                            valid_until=vu,
                        )
                        # We would ideally pass valid_from/valid_until to _handle_store_memory.
                        # Let's assume we can add it later or update it here.

                    from app.core.metrics import (
                        preference_conflicts_total,
                        preference_created_total,
                        preference_superseded_total,
                        preference_updated_total,
                    )
                    from app.memory.embeddings import embed_text

                    for p in data.get("preferences", []):
                        new_domain = p.get("domain", "general")
                        new_pref_text = p.get("preference", "")
                        new_conf = p.get("confidence", "MEDIUM")
                        new_strength = p.get("strength", 0.5)

                        new_emb = await embed_text(new_pref_text, task_type="RETRIEVAL_DOCUMENT")
                        if not new_emb:
                            continue

                        stmt = select(Preference, Preference.embedding.cosine_distance(new_emb).label("dist")).where(
                            Preference.user_id == user_id, Preference.status == "ACTIVE"
                        )
                        results = await session.execute(stmt)

                        handled = False
                        for row in results.all():
                            existing_pref = row[0]
                            dist = row[1]
                            sim = 1.0 - (dist if dist else 0.0)

                            if sim > 0.85 and existing_pref.domain == new_domain:
                                existing_pref.strength = min(1.0, existing_pref.strength + 0.1)
                                if new_conf == "HIGH":
                                    existing_pref.confidence = "HIGH"
                                preference_updated_total.inc()
                                preference_superseded_total.inc()
                                preference_conflicts_total.inc()
                                handled = True
                                break
                            elif sim > 0.7 and existing_pref.domain == new_domain:
                                existing_pref.status = "SUPERSEDED"
                                pref = Preference(
                                    user_id=user_id,
                                    domain=new_domain,
                                    preference=new_pref_text,
                                    confidence=new_conf,
                                    strength=new_strength,
                                    source="observed",
                                    embedding=new_emb,
                                    supersedes_preference_id=existing_pref.id,
                                )
                                session.add(pref)
                                handled = True
                                break

                        if not handled:
                            pref = Preference(
                                user_id=user_id,
                                domain=new_domain,
                                preference=new_pref_text,
                                confidence=new_conf,
                                strength=new_strength,
                                source="observed",
                                embedding=new_emb,
                            )
                            session.add(pref)
                            preference_created_total.inc()

                    await session.commit()
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
