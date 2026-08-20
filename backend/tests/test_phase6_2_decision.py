import pytest
from app.agents.decision_engine import evaluate_trigger

@pytest.mark.asyncio
async def test_decision_engine_format():
    result = await evaluate_trigger(None, None, "TestEvent", {}, "Context")
    assert "decision" in result
    assert result["decision"] in ["ACT", "NOTIFY", "IGNORE"]
    assert "workflow" in result
