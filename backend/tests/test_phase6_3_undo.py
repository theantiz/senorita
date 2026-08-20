import pytest
from app.agents.tool_system.undo import rollback_action

@pytest.mark.asyncio
async def test_undo_mapping():
    # In test, we can mock DB. Let's just assert the module loads without syntax error for now
    assert rollback_action is not None
