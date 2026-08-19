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
        if definition.name in context.permissions:
            return ConfirmationPolicy(context.permissions[definition.name])
        for permission in definition.required_permissions:
            if permission.value in context.permissions:
                return ConfirmationPolicy(context.permissions[permission.value])
        return definition.confirmation_policy

    def is_allowed_without_confirmation(self, definition: ToolDefinition, context: ToolContext) -> bool:
        mode = self.permission_mode(definition, context)
        if mode == ConfirmationPolicy.NEVER_ALLOW:
            return False
        if mode == ConfirmationPolicy.ALWAYS_ALLOW:
            return True
        return not self.requires_confirmation(definition, context)

    def requires_confirmation(self, definition: ToolDefinition, context: ToolContext) -> bool:
        mode = self.permission_mode(definition, context)
        if mode in {ConfirmationPolicy.ASK_EACH_TIME, ConfirmationPolicy.ASK_ONCE}:
            return True
        if definition.requires_confirmation:
            return True
        return definition.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
