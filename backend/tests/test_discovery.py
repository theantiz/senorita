import pytest

from app.agents.schemas import IntentSchema
from app.agents.tool_registry import get_tool_registry
from app.agents.tool_system.planner import ToolPlanner

pytestmark = pytest.mark.no_db


def test_tool_planner_discovery_without_intent():
    planner = ToolPlanner(get_tool_registry())
    discovered = planner.discover("send an email to Rahul")

    # Standard query should find send_email
    assert "send_email" in discovered


def test_tool_planner_discovery_with_intent_filtering():
    planner = ToolPlanner(get_tool_registry())

    # Create intent requesting communication capability
    intent = IntentSchema(
        intent="send_email",
        confidence=0.9,
        entities={},
        constraints=[],
        required_capabilities=["communication"],
        ambiguities=[],
        routing_decision="DIRECT_EXECUTION",
    )

    discovered = planner.discover("email Rahul", intent=intent)
    assert "send_email" in discovered

    # Intent searching for productivity should filter out email tools if search restricts by categories
    intent_productivity = IntentSchema(
        intent="create_task",
        confidence=0.9,
        entities={},
        constraints=[],
        required_capabilities=["productivity"],
        ambiguities=[],
        routing_decision="DIRECT_EXECUTION",
    )

    discovered_prod = planner.discover("email Rahul", intent=intent_productivity)
    # Since query is "email Rahul" but categories filter restricts to "productivity", send_email should NOT be included
    assert "send_email" not in discovered_prod
