from datetime import datetime, timedelta, timezone

import pytest

from app.agents.context import AgentContext
from app.agents.context_builder import build_context
from app.agents.schemas import IntentSchema
from app.db.models.memory_entry import MemoryEntry
from app.db.models.preference import Preference
from app.db.models.user import User


@pytest.fixture
async def phase5_3_user(db_session):
    u = User(name="Phase53User", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.mark.asyncio
async def test_preference_crud_and_supersession(db_session, phase5_3_user):
    from sqlalchemy import select

    from app.workers.memory_capture.implicit_capture import capture_implicit_memories

    # We will just manually test DB schema rules
    pref = Preference(
        user_id=phase5_3_user.id, domain="communication", preference="Keep it short", confidence="HIGH", status="ACTIVE"
    )
    db_session.add(pref)
    await db_session.commit()

    assert pref.status == "ACTIVE"
    assert pref.scope == "general"

    pref.status = "SUPERSEDED"
    pref2 = Preference(
        user_id=phase5_3_user.id,
        domain="communication",
        preference="Make it long",
        confidence="HIGH",
        status="ACTIVE",
        supersedes_preference_id=pref.id,
    )
    db_session.add(pref2)
    await db_session.commit()
    assert pref2.supersedes_preference_id == pref.id


@pytest.mark.asyncio
async def test_vector_context_retrieval(db_session, phase5_3_user, mocker):
    now = datetime.now(timezone.utc)

    m1 = MemoryEntry(
        user_id=phase5_3_user.id,
        content="I live in Bengaluru",
        memory_type="context",
        confidence="HIGH",
        valid_until=now + timedelta(days=5),
        embedding=[0.1] * 3072,
    )
    m2 = MemoryEntry(
        user_id=phase5_3_user.id,
        content="I like coffee",
        memory_type="context",
        confidence="HIGH",
        valid_until=now - timedelta(days=1),  # Expired!
        embedding=[0.1] * 3072,
    )
    db_session.add(m1)
    db_session.add(m2)

    p1 = Preference(
        user_id=phase5_3_user.id,
        domain="communication",
        preference="I prefer short answers",
        confidence="HIGH",
        embedding=[0.1] * 3072,
    )
    db_session.add(p1)
    await db_session.commit()

    # Mock embed_text
    mocker.patch("app.agents.context_builder.embed_text", return_value=[0.1] * 3072)

    intent = IntentSchema(
        intent="What city am I based in?",
        entities={},
        confidence=0.9,
        constraints=[],
        required_capabilities=[],
        ambiguities=[],
        routing_decision="DIRECT_EXECUTION",
    )
    ctx = AgentContext(
        user_id=str(phase5_3_user.id),
        conversation_id="conv1",
        request_id="req1",
        message="What city am I based in?",
        timezone="UTC",
        intent=intent,
    )

    context = await build_context(db_session, phase5_3_user, ctx)

    # Bengaluru should be there, coffee should NOT be there (expired)
    assert "Bengaluru" in context.enriched_context
    assert "coffee" not in context.enriched_context
    assert "I prefer short answers" in context.enriched_context
    assert context.context_metadata["memory_count"] == 1
    assert context.context_metadata["preference_count"] == 1
