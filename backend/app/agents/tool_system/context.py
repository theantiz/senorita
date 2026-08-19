from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ToolContext:
    user_id: UUID
    conversation_id: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid4()))
    timezone: str = "UTC"
    locale: str = "en-US"
    permissions: dict[str, str] = field(default_factory=dict)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    integration_context: dict[str, Any] = field(default_factory=dict)
    cancellation_token: str | None = None
    idempotency_key: str | None = None
