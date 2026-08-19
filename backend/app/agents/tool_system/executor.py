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
from app.agents.tool_system.persistence import (
    ToolPersistence,
    hash_idempotency_key,
    redact_sensitive_arguments,
    stable_hash,
)
from app.agents.tool_system.rate_limit import InMemoryRateLimiter
from app.agents.tool_system.registry import ToolRegistry
from app.agents.tool_system.result import ToolResult
from app.agents.tool_system.validation import SchemaValidationError, ToolArgumentValidator
from app.db.models import ToolIdempotencyKey, ToolInvocation

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
        persistence: ToolPersistence | None = None,
    ):
        self.registry = registry
        self.permission_manager = permission_manager or PermissionManager()
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.validator = validator or ToolArgumentValidator()
        self.rate_limiter = rate_limiter or InMemoryRateLimiter()
        self.metrics = metrics or ToolMetrics()
        self.persistence = persistence or ToolPersistence()

    async def execute(
        self,
        session: AsyncSession,
        context: ToolContext,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        confirmed: bool = False,
        confirmation_id: str | None = None,
        existing_invocation_id: Any | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        definition = self.registry.get(tool_name)
        if definition is None:
            result = ToolResult.fail(tool_name, "unknown_tool", f"Unknown tool `{tool_name}`.")
            if session is not None:
                await self.persistence.create_unknown_invocation(session, context, tool_name, arguments, result)
            return result

        retries = 0
        try:
            if session is None:
                result = await self._execute_once(session, context, definition, arguments, confirmed=confirmed)
                while self._should_retry(definition, result, retries):
                    retries += 1
                    await asyncio.sleep(definition.retry_policy.backoff_seconds * retries)
                    result = await self._execute_once(session, context, definition, arguments, confirmed=confirmed)
            else:
                result, retries = await self._execute_persisted(
                    session,
                    context,
                    definition,
                    arguments,
                    confirmed=confirmed,
                    confirmation_id=confirmation_id,
                    existing_invocation_id=existing_invocation_id,
                    start=start,
                )
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

        return await self._invoke_handler(session, context, definition, arguments)

    async def _invoke_handler(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> ToolResult:
        handler = self.registry.handler_for(definition.name)
        if handler is None:
            return ToolResult.fail(definition.name, "missing_handler", f"`{definition.name}` has no executor.")

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

    async def _execute_persisted(  # noqa: C901
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        *,
        confirmed: bool,
        confirmation_id: str | None,
        existing_invocation_id: Any | None,
        start: float,
    ) -> tuple[ToolResult, int]:
        handler = self.registry.handler_for(definition.name)
        idempotency_record: ToolIdempotencyKey | None = None
        key_hash = hash_idempotency_key(context.user_id, context.idempotency_key) if context.idempotency_key else None
        if key_hash and self._uses_idempotency(definition) and existing_invocation_id is None:
            existing_result = await self._prepare_idempotency_record(
                session, context, definition, arguments, context.idempotency_key or ""
            )
            if isinstance(existing_result, ToolResult):
                if existing_result.error and existing_result.error.code == "idempotency_conflict":
                    conflict_invocation = await self.persistence.create_invocation(
                        session,
                        context,
                        definition,
                        arguments,
                        idempotency_key_hash=key_hash,
                    )
                    await self.persistence.finish_invocation(
                        session,
                        conflict_invocation,
                        existing_result,
                        duration_ms=round((time.perf_counter() - start) * 1000, 2),
                        retries=0,
                    )
                return existing_result, 0
            idempotency_record = existing_result

        invocation = await self._resolve_invocation(
            session,
            context,
            definition,
            arguments,
            existing_invocation_id=existing_invocation_id,
            idempotency_key_hash=key_hash,
            confirmation_id=confirmation_id,
        )
        if isinstance(invocation, ToolResult):
            return invocation, 0

        if handler is None:
            result = ToolResult.fail(definition.name, "missing_handler", f"`{definition.name}` has no executor.")
            await self.persistence.finish_invocation(session, invocation, result, duration_ms=0, retries=0)
            if idempotency_record:
                await self.persistence.finish_idempotency_record(session, idempotency_record, invocation, result)
            return result, 0

        result = await self._validate_persisted_call(context, definition, arguments, confirmed, existing_invocation_id)
        if result:
            await self.persistence.finish_invocation(
                session,
                invocation,
                result,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                retries=0,
            )
            if idempotency_record:
                await self.persistence.finish_idempotency_record(session, idempotency_record, invocation, result)
            return result, 0

        try:
            arguments = self.validator.validate(definition.input_schema, arguments)
        except SchemaValidationError as exc:
            result = ToolResult.fail(definition.name, "invalid_input", str(exc))
            await self.persistence.finish_invocation(
                session,
                invocation,
                result,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                retries=0,
            )
            if idempotency_record:
                await self.persistence.finish_idempotency_record(session, idempotency_record, invocation, result)
            return result, 0

        if idempotency_record is None and invocation.idempotency_key_hash:
            idempotency_record = await self.persistence.get_idempotency_record_by_hash(
                session,
                context.user_id,
                invocation.idempotency_key_hash,
                lock=True,
            )

        if idempotency_record and idempotency_record.tool_invocation_id is None:
            idempotency_record.tool_invocation_id = invocation.id

        if self.permission_manager.requires_confirmation(definition, context) and not confirmed:
            confirmation = await self.persistence.create_confirmation(
                session, context, definition, invocation, arguments
            )
            result = ToolResult.fail(
                definition.name,
                "confirmation_required",
                f"`{definition.name}` requires confirmation before execution.",
                data={
                    "tool": definition.name,
                    "risk": definition.risk_level.value,
                    "side_effects": list(definition.side_effects),
                    "request_id": context.request_id,
                    "confirmation_id": str(confirmation.id),
                    "tool_invocation_id": str(invocation.id),
                    "expires_at": confirmation.expires_at.isoformat(),
                    "arguments_preview": confirmation.arguments_preview,
                },
                metadata={
                    "confirmation_required": True,
                    "confirmation_id": str(confirmation.id),
                    "tool_invocation_id": str(invocation.id),
                },
            )
            if idempotency_record:
                idempotency_record.status = "WAITING_CONFIRMATION"
                idempotency_record.result = result.to_dict()
            await session.flush()
            return result, 0

        if not self.rate_limiter.allow(context.user_id, definition):
            result = ToolResult.fail(
                definition.name, "rate_limited", f"`{definition.name}` is rate limited.", retryable=True
            )
            await self.persistence.finish_invocation(
                session,
                invocation,
                result,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                retries=0,
            )
            if idempotency_record:
                await self.persistence.finish_idempotency_record(session, idempotency_record, invocation, result)
            return result, 0

        retries = 0
        await self.persistence.start_invocation(session, invocation)
        result = await self._invoke_handler(session, context, definition, arguments)
        while self._should_retry(definition, result, retries):
            retries += 1
            invocation.retry_count = retries
            await session.flush()
            await asyncio.sleep(definition.retry_policy.backoff_seconds * retries)
            result = await self._invoke_handler(session, context, definition, arguments)

        await self.persistence.finish_invocation(
            session,
            invocation,
            result,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            retries=retries,
        )
        if idempotency_record:
            await self.persistence.finish_idempotency_record(session, idempotency_record, invocation, result)
        return result, retries

    async def _prepare_idempotency_record(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        key: str,
    ) -> ToolIdempotencyKey | ToolResult:
        record, is_new_key = await self.persistence.get_or_create_idempotency_record(
            session, context, definition, arguments, key
        )
        fingerprint = self._request_fingerprint(definition, arguments)
        if record.request_fingerprint != fingerprint:
            return ToolResult.fail(
                definition.name,
                "idempotency_conflict",
                "Idempotency key was already used for different tool arguments.",
            )
        if not is_new_key:
            result = self.persistence.result_for_existing_idempotency_record(definition, record)
            if result:
                return result
        return record

    async def _validate_persisted_call(
        self,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        confirmed: bool,
        existing_invocation_id: Any | None,
    ) -> ToolResult | None:
        if not self.permission_manager.is_tool_enabled(definition):
            return ToolResult.fail(definition.name, "tool_disabled", f"`{definition.name}` is disabled.")

        mode = self.permission_manager.permission_mode(definition, context)
        if mode == ConfirmationPolicy.NEVER_ALLOW:
            return ToolResult.fail(definition.name, "permission_denied", f"`{definition.name}` is not allowed.")
        if (
            self.permission_manager.requires_confirmation(definition, context)
            and confirmed
            and existing_invocation_id is None
        ):
            return ToolResult.fail(
                definition.name,
                "confirmation_invocation_required",
                "Confirmed execution requires approving the original tool invocation.",
            )
        return None

    async def _resolve_invocation(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        *,
        existing_invocation_id: Any | None,
        idempotency_key_hash: str | None,
        confirmation_id: str | None,
    ) -> ToolInvocation | ToolResult:
        if existing_invocation_id is None:
            return await self.persistence.create_invocation(
                session,
                context,
                definition,
                arguments,
                idempotency_key_hash=idempotency_key_hash,
            )

        invocation = await self.persistence.get_invocation_for_update(session, existing_invocation_id, context.user_id)
        if not invocation:
            return ToolResult.fail(definition.name, "invocation_not_found", "Tool invocation not found.")
        if invocation.tool_name != definition.name:
            return ToolResult.fail(definition.name, "invocation_mismatch", "Confirmation does not match this tool.")
        if invocation.arguments_hash != stable_hash(redact_sensitive_arguments(arguments)):
            return ToolResult.fail(
                definition.name, "invocation_mismatch", "Confirmation does not match these arguments."
            )
        if not invocation.confirmation_id:
            return ToolResult.fail(definition.name, "confirmation_not_found", "Tool invocation has no confirmation.")
        if confirmation_id is not None and str(invocation.confirmation_id) != str(confirmation_id):
            return ToolResult.fail(
                definition.name, "confirmation_mismatch", "Confirmation does not match this invocation."
            )
        if invocation.status != "WAITING_CONFIRMATION":
            return ToolResult.fail(
                definition.name,
                "invocation_not_waiting",
                "Tool invocation is not waiting for confirmation.",
            )
        return invocation

    def _uses_idempotency(self, definition: ToolDefinition) -> bool:
        return bool(definition.side_effects) or not definition.idempotent

    def _request_fingerprint(self, definition: ToolDefinition, arguments: dict[str, Any]) -> str:
        return stable_hash(
            {
                "tool_name": definition.name,
                "tool_version": definition.version,
                "arguments": redact_sensitive_arguments(arguments),
            }
        )

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
