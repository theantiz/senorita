from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tool_system.confirmation import ConfirmationManager
from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.definitions import ConfirmationPolicy, ToolDefinition
from app.agents.tool_system.metrics import ToolMetrics
from app.agents.tool_system.permissions import PermissionManager
from app.agents.tool_system.rate_limit import InMemoryRateLimiter
from app.agents.tool_system.registry import ToolRegistry
from app.agents.tool_system.result import ToolResult
from app.agents.tool_system.validation import SchemaValidationError, ToolArgumentValidator

logger = logging.getLogger("senorita.tools.executor")


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        permission_manager: PermissionManager | None = None,
        confirmation_manager: ConfirmationManager | None = None,
        validator: ToolArgumentValidator | None = None,
        rate_limiter: InMemoryRateLimiter | None = None,
        metrics: ToolMetrics | None = None,
    ):
        self.registry = registry
        self.permission_manager = permission_manager or PermissionManager()
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.validator = validator or ToolArgumentValidator()
        self.rate_limiter = rate_limiter or InMemoryRateLimiter()
        self.metrics = metrics or ToolMetrics()

    async def execute(
        self,
        session: AsyncSession,
        context: ToolContext,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        confirmed: bool = False,
    ) -> ToolResult:
        start = time.perf_counter()
        definition = self.registry.get(tool_name)
        if definition is None:
            return ToolResult.fail(tool_name, "unknown_tool", f"Unknown tool `{tool_name}`.")

        retries = 0
        try:
            result = await self._execute_once(session, context, definition, arguments, confirmed=confirmed)
            while self._should_retry(definition, result, retries):
                retries += 1
                await asyncio.sleep(definition.retry_policy.backoff_seconds * retries)
                result = await self._execute_once(session, context, definition, arguments, confirmed=confirmed)
            return result
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            success = "result" in locals() and result.success
            self.metrics.record(tool_name, success=success, duration_ms=duration_ms, retries=retries)
            self._log_invocation(context, definition, arguments, duration_ms, success, retries)

    async def _execute_once(  # noqa: C901
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        *,
        confirmed: bool,
    ) -> ToolResult:
        handler = self.registry.handler_for(definition.name)
        if handler is None:
            return ToolResult.fail(definition.name, "missing_handler", f"`{definition.name}` has no executor.")

        if not self.permission_manager.is_tool_enabled(definition):
            return ToolResult.fail(definition.name, "tool_disabled", f"`{definition.name}` is disabled.")

        try:
            arguments = self.validator.validate(definition.input_schema, arguments)
        except SchemaValidationError as exc:
            return ToolResult.fail(definition.name, "invalid_input", str(exc))

        mode = self.permission_manager.permission_mode(definition, context)
        if mode == ConfirmationPolicy.NEVER_ALLOW:
            return ToolResult.fail(definition.name, "permission_denied", f"`{definition.name}` is not allowed.")

        if self.permission_manager.requires_confirmation(definition, context) and not confirmed:
            return self.confirmation_manager.require_confirmation(definition, arguments, context)

        if not self.rate_limiter.allow(context.user_id, definition):
            return ToolResult.fail(
                definition.name, "rate_limited", f"`{definition.name}` is rate limited.", retryable=True
            )

        try:
            raw = await asyncio.wait_for(
                handler(session, context.user_id, **arguments),
                timeout=definition.timeout_seconds,
            )
        except ValueError as exc:
            return ToolResult.fail(definition.name, "invalid_input", str(exc))
        except TimeoutError:
            return ToolResult.fail(definition.name, "timeout", f"`{definition.name}` timed out.", retryable=True)
        except Exception:
            logger.exception("Tool %s failed", definition.name)
            return ToolResult.fail(definition.name, "tool_failed", f"`{definition.name}` failed. See server logs.")

        metadata = {
            "provider": definition.provider,
            "request_id": context.request_id,
            "confirmation_required": definition.requires_confirmation,
        }
        if isinstance(raw, dict) and "error" in raw:
            error_value = raw["error"]
            if isinstance(error_value, dict):
                code = str(error_value.get("code") or raw.get("code") or "tool_error")
                message = str(error_value.get("message") or "Tool failed.")
            else:
                code = str(raw.get("code") or error_value or "tool_error")
                message = str(error_value)
            return ToolResult.fail(definition.name, code, message, data=raw, metadata=metadata)

        return ToolResult.ok(definition.name, raw, metadata=metadata)

    def _should_retry(self, definition: ToolDefinition, result: ToolResult, retries: int) -> bool:
        if result.success or not result.error:
            return False
        if retries >= definition.retry_policy.max_retries:
            return False
        return result.error.retryable and result.error.code in definition.retry_policy.retryable_error_codes

    def _log_invocation(
        self,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        duration_ms: float,
        success: bool,
        retries: int,
    ) -> None:
        argument_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True, default=str).encode()).hexdigest()[:16]
        logger.info(
            "tool_call",
            extra={
                "request_id": context.request_id,
                "user_id": str(context.user_id),
                "conversation_id": context.conversation_id,
                "tool_name": definition.name,
                "arguments_hash": argument_hash,
                "duration_ms": duration_ms,
                "success": success,
                "provider": definition.provider,
                "retry_count": retries,
                "confirmation_required": definition.requires_confirmation,
            },
        )
