from uuid import uuid4

import pytest

from app.agents.tool_registry import discover_tools_for_message, get_tool_inventory, get_tool_registry
from app.agents.tool_system import (
    ConfirmationPolicy,
    RiskLevel,
    ToolContext,
    ToolDefinition,
    ToolExecutor,
    ToolPermission,
)
from app.agents.tool_system.registry import ToolRegistry

pytestmark = pytest.mark.no_db


async def _ok_handler(session, user_id, name: str):
    return {"hello": name, "user_id": str(user_id)}


async def _error_handler(session, user_id):
    return {"error": "provider unavailable", "code": "provider_unavailable"}


def _definition(**overrides):
    values = {
        "name": "hello_tool",
        "description": "Say hello.",
        "category": "test",
        "subcategory": "unit",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        "required_permissions": (ToolPermission.READ,),
    }
    values.update(overrides)
    return ToolDefinition(**values)


async def test_tool_executor_normalizes_success_result():
    registry = ToolRegistry()
    registry.register(_definition(), _ok_handler)
    executor = ToolExecutor(registry)
    user_id = uuid4()

    result = await executor.execute(None, ToolContext(user_id=user_id), "hello_tool", {"name": "Jay"})

    assert result.success is True
    assert result.to_dict()["data"]["hello"] == "Jay"
    assert result.to_dict()["metadata"]["provider"] == "local"


async def test_tool_executor_rejects_unknown_arguments():
    registry = ToolRegistry()
    registry.register(_definition(), _ok_handler)
    executor = ToolExecutor(registry)

    result = await executor.execute(None, ToolContext(user_id=uuid4()), "hello_tool", {"name": "Jay", "extra": True})

    assert result.success is False
    assert result.error.code == "invalid_input"


async def test_tool_executor_requires_confirmation_for_high_risk_tools():
    registry = ToolRegistry()
    registry.register(
        _definition(
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            confirmation_policy=ConfirmationPolicy.ASK_EACH_TIME,
        ),
        _ok_handler,
    )
    executor = ToolExecutor(registry)

    result = await executor.execute(None, ToolContext(user_id=uuid4()), "hello_tool", {"name": "Jay"})

    assert result.success is False
    assert result.error.code == "confirmation_required"
    assert result.metadata["confirmation_required"] is True


async def test_tool_executor_normalizes_handler_errors():
    registry = ToolRegistry()
    registry.register(
        _definition(name="failing_tool", input_schema={"type": "object", "properties": {}, "required": []}),
        _error_handler,
    )
    executor = ToolExecutor(registry)

    result = await executor.execute(None, ToolContext(user_id=uuid4()), "failing_tool", {})

    assert result.success is False
    assert result.error.code == "provider_unavailable"


def test_global_tool_registry_has_metadata_inventory():
    inventory = get_tool_inventory()

    assert any(row["tool"] == "send_email" and row["risk"] == "HIGH" for row in inventory)
    assert any(row["tool"] == "morning_brief" and row["category"] == "orchestration" for row in inventory)


def test_dynamic_discovery_expands_dependencies():
    discovered = discover_tools_for_message("schedule a meeting with Rahul next week")

    assert "create_calendar_event" in discovered
    assert "find_contact" in discovered
    assert "check_conflicts" in discovered


def test_registry_categories_are_structured():
    categories = get_tool_registry().categories()

    assert "communication" in categories
    assert "productivity" in categories
    assert "research" in categories
