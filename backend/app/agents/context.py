from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentContext:
    user_id: str
    conversation_id: str | None
    request_id: str
    message: str
    timezone: str
    locale: str = "en"
    permissions: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
