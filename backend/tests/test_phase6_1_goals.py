import pytest
from datetime import datetime, timezone
from app.db.models.user import User
from app.db.models.goal import Goal
from app.agents.context import AgentContext
from app.agents.schemas import IntentSchema
from app.agents.context_builder import build_context

@pytest.fixture
async def phase6_user(db_session):
    u = User(name="Phase6User", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.mark.asyncio
async def test_goal_embedding_and_retrieval(db_session, phase6_user, mocker):
    g1 = Goal(
        user_id=phase6_user.id,
        name="Launch Meetra",
        description="Launch by October",
        embedding=[0.1]*3072,
        status="ACTIVE"
    )
    db_session.add(g1)
    await db_session.commit()
    
    mocker.patch('app.agents.context_builder.embed_text', return_value=[0.1]*3072)
    
    intent = IntentSchema(
        intent="What are my goals?",
        entities={}, confidence=0.9,
        constraints=[], required_capabilities=[], ambiguities=[], routing_decision="DIRECT_EXECUTION"
    )
    ctx = AgentContext(
        user_id=str(phase6_user.id),
        conversation_id="conv1",
        request_id="req1",
        message="What are my goals?",
        timezone="UTC",
        intent=intent
    )
    context = await build_context(db_session, phase6_user, ctx)
    print("GOALS: ", context.goals)
    assert "Launch Meetra" in context.enriched_context
    assert context.context_metadata.get("goal_count", 0) == 1
