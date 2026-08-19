from __future__ import annotations

from app.agents.tool_system.definitions import ToolDefinition


def tool_health(definition: ToolDefinition, *, enabled: bool = True) -> dict[str, str]:
    if not enabled:
        return {"status": "disabled", "tool": definition.name, "provider": definition.provider}
    return {"status": "available", "tool": definition.name, "provider": definition.provider}
