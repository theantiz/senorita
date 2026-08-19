from __future__ import annotations

from typing import Any

from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.definitions import ToolDefinition
from app.agents.tool_system.result import ToolResult


class ConfirmationManager:
    def require_confirmation(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        return ToolResult.fail(
            definition.name,
            "confirmation_required",
            f"`{definition.name}` requires confirmation before execution.",
            data={
                "tool": definition.name,
                "arguments": arguments,
                "risk": definition.risk_level.value,
                "side_effects": list(definition.side_effects),
                "request_id": context.request_id,
            },
            metadata={"confirmation_required": True},
        )
