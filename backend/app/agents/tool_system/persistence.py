from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.definitions import ToolDefinition
from app.agents.tool_system.result import ToolResult
from app.db.models import ToolConfirmation, ToolIdempotencyKey, ToolInvocation

SENSITIVE_ARGUMENT_KEYS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "cookie",
    "credentials",
    "password",
    "refresh_token",
    "secret",
    "token",
)
REDACTED_VALUE = "[REDACTED]"
CONFIRMATION_TTL_MINUTES = 15


def utcnow() -> datetime:
    return datetime.now(UTC)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def hash_idempotency_key(user_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{user_id}:{key}".encode()).hexdigest()


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_ARGUMENT_KEYS)


def redact_sensitive_arguments(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = REDACTED_VALUE
            else:
                redacted[key] = redact_sensitive_arguments(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_arguments(item) for item in value]
    return value


def preview_arguments(value: Any, *, max_string_length: int = 500) -> Any:
    redacted = redact_sensitive_arguments(value)
    if isinstance(redacted, dict):
        return {key: preview_arguments(item, max_string_length=max_string_length) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [preview_arguments(item, max_string_length=max_string_length) for item in redacted[:20]]
    if isinstance(redacted, str) and len(redacted) > max_string_length:
        return f"{redacted[:max_string_length]}... [truncated {len(redacted) - max_string_length} chars]"
    return redacted


def build_confirmation_summary(definition: ToolDefinition) -> str:
    effects = ", ".join(definition.side_effects) if definition.side_effects else definition.description
    return f"{definition.name} requires approval because it may perform: {effects}."


class ToolPersistence:
    async def create_invocation(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        *,
        idempotency_key_hash: str | None = None,
        status: str = "PENDING",
    ) -> ToolInvocation:
        safe_arguments = redact_sensitive_arguments(arguments)
        invocation = ToolInvocation(
            request_id=context.request_id,
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            tool_name=definition.name,
            tool_version=definition.version,
            status=status,
            arguments_hash=stable_hash(safe_arguments),
            arguments_snapshot=safe_arguments,
            risk_level=definition.risk_level.value,
            confirmation_required=definition.requires_confirmation,
            provider=definition.provider,
            idempotency_key_hash=idempotency_key_hash,
        )
        session.add(invocation)
        await session.flush()
        return invocation

    async def create_unknown_invocation(
        self,
        session: AsyncSession,
        context: ToolContext,
        tool_name: str,
        arguments: dict[str, Any],
        result: ToolResult,
    ) -> ToolInvocation:
        safe_arguments = redact_sensitive_arguments(arguments)
        invocation = ToolInvocation(
            request_id=context.request_id,
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            tool_name=tool_name,
            tool_version="unknown",
            status="FAILED",
            arguments_hash=stable_hash(safe_arguments),
            arguments_snapshot=safe_arguments,
            result=result.to_dict(),
            error_code=result.error.code if result.error else None,
            error_message=result.error.message if result.error else None,
            risk_level="LOW",
            confirmation_required=False,
            provider="unknown",
            completed_at=utcnow(),
            duration_ms=0,
            retry_count=0,
        )
        session.add(invocation)
        await session.flush()
        return invocation

    async def create_confirmation(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        invocation: ToolInvocation,
        arguments: dict[str, Any],
    ) -> ToolConfirmation:
        confirmation = ToolConfirmation(
            user_id=context.user_id,
            conversation_id=context.conversation_id,
            tool_invocation_id=invocation.id,
            tool_name=definition.name,
            risk_level=definition.risk_level.value,
            summary=build_confirmation_summary(definition),
            arguments_preview=preview_arguments(arguments),
            status="PENDING",
            expires_at=utcnow() + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
        )
        session.add(confirmation)
        await session.flush()
        invocation.status = "WAITING_CONFIRMATION"
        invocation.confirmation_id = confirmation.id
        await session.flush()
        return confirmation

    async def get_confirmation_for_user(
        self, session: AsyncSession, user_id: UUID, confirmation_id: UUID, *, lock: bool = False
    ) -> ToolConfirmation | None:
        stmt = select(ToolConfirmation).where(
            ToolConfirmation.id == confirmation_id, ToolConfirmation.user_id == user_id
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_invocation_for_update(
        self, session: AsyncSession, invocation_id: UUID, user_id: UUID
    ) -> ToolInvocation | None:
        result = await session.execute(
            select(ToolInvocation)
            .where(ToolInvocation.id == invocation_id, ToolInvocation.user_id == user_id)
            .with_for_update()
        )
        return result.scalars().first()

    async def start_invocation(self, session: AsyncSession, invocation: ToolInvocation) -> None:
        invocation.status = "RUNNING"
        invocation.started_at = utcnow()
        await session.flush()

    async def finish_invocation(
        self,
        session: AsyncSession,
        invocation: ToolInvocation,
        result: ToolResult,
        *,
        duration_ms: float,
        retries: int,
    ) -> None:
        invocation.status = "SUCCESS" if result.success else "FAILED"
        invocation.result = result.to_dict()
        invocation.error_code = result.error.code if result.error else None
        invocation.error_message = result.error.message if result.error else None
        invocation.completed_at = utcnow()
        invocation.duration_ms = round(duration_ms)
        invocation.retry_count = retries
        await session.flush()

    async def get_or_create_idempotency_record(
        self,
        session: AsyncSession,
        context: ToolContext,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        key: str,
    ) -> tuple[ToolIdempotencyKey, bool]:
        key_hash = hash_idempotency_key(context.user_id, key)
        fingerprint = stable_hash(
            {
                "tool_name": definition.name,
                "tool_version": definition.version,
                "arguments": redact_sensitive_arguments(arguments),
            }
        )
        stmt = (
            insert(ToolIdempotencyKey)
            .values(
                user_id=context.user_id,
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                tool_name=definition.name,
                status="PENDING",
            )
            .on_conflict_do_nothing(index_elements=["user_id", "key_hash"])
            .returning(ToolIdempotencyKey.id)
        )
        inserted = (await session.execute(stmt)).scalar_one_or_none()
        result = await session.execute(
            select(ToolIdempotencyKey)
            .where(ToolIdempotencyKey.user_id == context.user_id, ToolIdempotencyKey.key_hash == key_hash)
            .with_for_update()
        )
        record = result.scalars().one()
        return record, inserted is not None

    def result_for_existing_idempotency_record(
        self, definition: ToolDefinition, record: ToolIdempotencyKey
    ) -> ToolResult | None:
        if record.status in {"SUCCESS", "FAILED", "WAITING_CONFIRMATION"} and record.result:
            return ToolResult.from_dict(record.result)
        if record.status in {"CANCELLED", "EXPIRED"}:
            return ToolResult.fail(
                definition.name,
                f"idempotency_{record.status.lower()}",
                f"Idempotency key refers to a {record.status.lower()} invocation.",
            )
        return None

    async def finish_idempotency_record(
        self, session: AsyncSession, record: ToolIdempotencyKey, invocation: ToolInvocation, result: ToolResult
    ) -> None:
        record.tool_invocation_id = invocation.id
        record.status = invocation.status
        record.result = result.to_dict()
        record.error_code = result.error.code if result.error else None
        record.error_message = result.error.message if result.error else None
        record.completed_at = utcnow() if invocation.status in {"SUCCESS", "FAILED", "CANCELLED", "EXPIRED"} else None
        await session.flush()

    async def wait_idempotency_record(
        self, session: AsyncSession, context: ToolContext, key_hash: str
    ) -> ToolIdempotencyKey:
        result = await session.execute(
            select(ToolIdempotencyKey)
            .where(ToolIdempotencyKey.user_id == context.user_id, ToolIdempotencyKey.key_hash == key_hash)
            .with_for_update()
        )
        return result.scalars().one()

    async def get_idempotency_record_by_hash(
        self, session: AsyncSession, user_id: UUID, key_hash: str, *, lock: bool = False
    ) -> ToolIdempotencyKey | None:
        stmt = select(ToolIdempotencyKey).where(
            ToolIdempotencyKey.user_id == user_id,
            ToolIdempotencyKey.key_hash == key_hash,
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().first()
