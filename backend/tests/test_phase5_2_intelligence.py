from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.agents.context_builder import build_context
from app.db.models.memory_entry import MemoryEntry
from app.db.models.preference import Preference
from app.db.models.user import User


@pytest.mark.asyncio
async def test_preference_schema(db_session):
    # Test preference insertion
    user = User(name="PrefUser", timezone="UTC")
    db_session.add(user)
    await db_session.commit()

    pref = Preference(
        user_id=user.id, domain="communication", preference="Prefers concise messages", confidence="HIGH", strength=0.9
    )
    db_session.add(pref)
    await db_session.commit()

    assert pref.id is not None
    assert pref.confidence == "HIGH"
    assert pref.strength == 0.9


@pytest.mark.asyncio
async def test_temporal_memory(db_session):
    user = User(name="TempUser", timezone="UTC")
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    mem = MemoryEntry(
        user_id=user.id,
        content="Is visiting London",
        memory_type="context",
        confidence="HIGH",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=5),
        importance_score=0.8,
    )
    db_session.add(mem)
    await db_session.commit()

    assert mem.valid_from is not None
    assert mem.valid_until is not None


@pytest.mark.asyncio
async def test_context_builder(db_session, mocker):
    mocker.patch("app.agents.context_builder.embed_text", return_value=[0.1] * 3072)
    user = User(name="ContextUser", timezone="UTC")
    db_session.add(user)
    await db_session.commit()

    pref = Preference(user_id=user.id, domain="coding", preference="Use Python exclusively", confidence="HIGH")
    db_session.add(pref)

    now = datetime.now(timezone.utc)
    mem = MemoryEntry(
        user_id=user.id,
        content="Currently working on Phase 5.2",
        memory_type="context",
        confidence="HIGH",
        valid_until=now + timedelta(days=1),
        importance_score=1.0,
    )
    db_session.add(mem)
    await db_session.commit()

    from app.agents.context import AgentContext
    from app.agents.schemas import IntentSchema

    intent = IntentSchema(
        intent="Write a python script",
        entities={},
        confidence=0.9,
        constraints=[],
        required_capabilities=["documents"],
        ambiguities=[],
        routing_decision="DIRECT_EXECUTION",
    )

    ctx = AgentContext(
        user_id=str(user.id),
        conversation_id="conv1",
        request_id="req1",
        message="Write a script",
        timezone="UTC",
        intent=intent,
    )

    context = await build_context(db_session, user, ctx)

    assert "RELEVANT PREFERENCES" in context.enriched_context
    assert "Use Python exclusively" in context.enriched_context
    assert "RELEVANT MEMORIES" in context.enriched_context
    assert "Phase 5.2" in context.enriched_context
