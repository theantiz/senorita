from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfirmationPolicy(StrEnum):
    ALWAYS_ALLOW = "always_allow"
    ASK_ONCE = "ask_once"
    ASK_EACH_TIME = "ask_each_time"
    NEVER_ALLOW = "never_allow"


class ToolPermission(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    SEND = "SEND"
    DELETE = "DELETE"
    SYSTEM = "SYSTEM"
    MEMORY = "MEMORY"
    COMMUNICATION = "COMMUNICATION"
    RESEARCH = "RESEARCH"
    DOCUMENT = "DOCUMENT"
    DEVELOPER = "DEVELOPER"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    backoff_seconds: float = 0.25
    jitter_seconds: float = 0.0
    retryable_error_codes: tuple[str, ...] = ("timeout", "provider_unavailable", "rate_limited")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    category: str
    subcategory: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_permissions: tuple[ToolPermission, ...] = ()
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_policy: ConfirmationPolicy = ConfirmationPolicy.ALWAYS_ALLOW
    supports_async: bool = True
    supports_streaming: bool = False
    timeout_seconds: float = 20.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    rate_limit_per_minute: int | None = None
    idempotent: bool = True
    side_effects: tuple[str, ...] = ()
    supported_platforms: tuple[str, ...] = ("Windows", "Darwin", "Linux")
    dependencies: tuple[str, ...] = ()
    provider: str = "local"
    enabled: bool = True
    version: str = "1.0"
    aliases: tuple[str, ...] = ()
    cacheable: bool = False
    cache_ttl_seconds: int | None = None

    def searchable_text(self) -> str:
        parts = [
            self.name,
            self.description,
            self.category,
            self.subcategory,
            self.provider,
            *self.aliases,
            *self.dependencies,
        ]
        return " ".join(parts).replace("_", " ").lower()

    def to_inventory_row(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "risk": self.risk_level.value,
            "confirmation": self.confirmation_policy.value,
            "permission": [permission.value for permission in self.required_permissions],
            "provider": self.provider,
            "status": "enabled" if self.enabled else "disabled",
            "version": self.version,
        }
