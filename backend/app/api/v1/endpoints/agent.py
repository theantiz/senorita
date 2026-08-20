from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext
from app.agents.context_builder import build_context
from app.agents.intent import extract_intent
from app.agents.llm_provider import GeminiProvider
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()


@router.get("/context/preview")
async def preview_context(
    message: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Preview the intent and gathered context without executing an action."""
    ctx = AgentContext(
        user_id=str(current_user.id),
        conversation_id="preview",
        request_id="preview",
        message=message,
        timezone=current_user.timezone,
    )
    provider = GeminiProvider()
    intent = await extract_intent(ctx, provider)
    ctx.intent = intent

    ctx = await build_context(db, current_user, ctx)

    # Do not return enriched_context as it contains system instructions.
    # Return structured items and metadata.
    return {
        "intent_extracted": intent.intent,
        "entities": intent.entities,
        "routing_decision": intent.routing_decision,
        "memories": ctx.memories,
        "preferences": ctx.preferences,
        "calendar_events": ctx.calendar_events,
        "tasks": ctx.tasks,
        "metadata": ctx.context_metadata,
    }
