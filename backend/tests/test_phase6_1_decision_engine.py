import pytest
from app.agents.decision_engine import evaluate_trigger

@pytest.mark.asyncio
async def test_decision_engine_fallback():
    # Test that the fallback error handler returns standard shape
    result = await evaluate_trigger(None, None, "TestEvent", {}, "Context")
    assert result["should_act"] == False
    assert result["is_urgent"] == False
    assert "Error" in result["reasoning"]
