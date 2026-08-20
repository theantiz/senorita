import pytest
from app.agents.decision_engine import evaluate_trigger

@pytest.mark.asyncio
async def test_decision_engine_fallback():
    # Test that the fallback error handler returns standard shape
    result = await evaluate_trigger(None, None, "TestEvent", {}, "Context")
    assert result["decision"] == "IGNORE"
    assert "Error" in result["reason"]
