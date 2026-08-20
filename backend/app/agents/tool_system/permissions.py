from __future__ import annotations

import os

from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.definitions import ConfirmationPolicy, RiskLevel, ToolDefinition


class PermissionManager:
    def __init__(self, env: dict[str, str] | None = None):
        self._env = env if env is not None else os.environ

    def is_tool_enabled(self, definition: ToolDefinition) -> bool:
        if not definition.enabled:
            return False
        env_name = f"ENABLE_{definition.provider.upper()}_TOOLS"
        if definition.provider in {"local", "database"}:
            env_name = f"ENABLE_{definition.category.upper()}_TOOLS"
        value = self._env.get(env_name)
        if value is None:
            return True
        return value.strip().lower() not in {"0", "false", "no", "off"}


    def permission_mode(self, definition: ToolDefinition, context: ToolContext) -> ConfirmationPolicy:
        return ConfirmationPolicy.ALWAYS_ALLOW

    def is_allowed_without_confirmation(self, definition: ToolDefinition, context: ToolContext) -> bool:
        return True

    def requires_confirmation(self, definition: ToolDefinition, context: ToolContext) -> bool:
        return False
