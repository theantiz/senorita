from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.context import AgentContext
from app.agents.intent import extract_intent
from app.agents.llm_provider import LLMProvider
from app.agents.schemas import IntentSchema

pytestmark = pytest.mark.no_db


def test_agent_context_instantiation():
    ctx = AgentContext(
        user_id="user-123",
        conversation_id="conv-456",
        request_id="req-789",
        message="Hello Senorita",
        timezone="UTC",
    )
    assert ctx.user_id == "user-123"
    assert ctx.message == "Hello Senorita"
    assert ctx.timezone == "UTC"
    assert ctx.locale == "en"


@pytest.mark.asyncio
async def test_extract_intent_success():
    ctx = AgentContext(
        user_id="user-123",
        conversation_id="conv-456",
        request_id="req-789",
        message="Schedule a meeting with John tomorrow at 9 AM",
        timezone="UTC",
        recent_messages=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello, baby."}
        ]
    )

    mock_intent = IntentSchema(
        intent="schedule_meeting",
        confidence=0.95,
        entities={"person": "John", "time": "tomorrow at 9 AM"},
        constraints=[],
        required_capabilities=["calendar", "contacts"],
        ambiguities=[],
        routing_decision="MULTI_STEP_PLAN"
    )

    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured = AsyncMock(return_value=mock_intent)

    result = await extract_intent(ctx, mock_provider)

    assert result.intent == "schedule_meeting"
    assert result.confidence == 0.95
    assert result.entities["person"] == "John"
    assert "calendar" in result.required_capabilities
    assert not result.ambiguities
    mock_provider.generate_structured.assert_called_once()
