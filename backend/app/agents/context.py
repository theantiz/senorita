from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.schemas import IntentSchema


@dataclass
class AgentContext:
    user_id: str
    conversation_id: str | None
    request_id: str
    message: str
    timezone: str
    current_time: str = ""
    locale: str = "en"

    intent: Optional[IntentSchema] = None

    memories: list[dict[str, Any]] = field(default_factory=list)
    preferences: list[dict[str, Any]] = field(default_factory=list)
    calendar_events: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    contacts: list[dict[str, Any]] = field(default_factory=list)
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    integration_state: list[dict[str, Any]] = field(default_factory=list)

    context_metadata: dict[str, Any] = field(default_factory=dict)
    enriched_context: str = ""
