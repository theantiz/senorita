"""
Normalised provider error hierarchy for Señorita.

All integration adapters (Gmail, Slack, Calendar, etc.) must catch
SDK-specific exceptions and re-raise one of these types so that:

1. The frontend receives a safe, human-readable message.
2. The retry policy can distinguish transient from permanent failures.
3. Stack traces / SDK internals never reach the client.

Usage:
    from app.core.errors import ProviderRateLimitError, normalize_provider_error
"""

from __future__ import annotations

from typing import Any

# ─── Base ─────────────────────────────────────────────────────────────────────


class SeñoritaError(Exception):
    """Base class for all application-level errors."""

    public_message: str = "An unexpected error occurred. Please try again."
    http_status: int = 500
    error_code: str = "internal_error"
    retryable: bool = False

    def __init__(self, detail: str | None = None, *, cause: Exception | None = None):
        self.detail = detail or self.public_message
        self.cause = cause
        super().__init__(self.detail)


# ─── Provider errors (transient) ──────────────────────────────────────────────


class ProviderError(SeñoritaError):
    """Base for all provider-side errors."""

    public_message = "An external service is temporarily unavailable."
    error_code = "provider_error"


class ProviderRateLimitError(ProviderError):
    """Provider returned 429 / rate limit exceeded."""

    public_message = "We're being rate-limited by an external service. Please try again shortly."
    http_status = 429
    error_code = "provider_rate_limited"
    retryable = True


class ProviderTimeoutError(ProviderError):
    """Provider request timed out."""

    public_message = "An external service took too long to respond."
    http_status = 504
    error_code = "provider_timeout"
    retryable = True


class ProviderUnavailableError(ProviderError):
    """Provider returned 5xx or is unreachable."""

    public_message = "An external service is currently unavailable. Please try again later."
    http_status = 503
    error_code = "provider_unavailable"
    retryable = True


# ─── Provider errors (permanent) ──────────────────────────────────────────────


class ProviderAuthenticationError(ProviderError):
    """OAuth token expired or invalid."""

    public_message = "Your connection to an external service needs to be renewed."
    http_status = 401
    error_code = "provider_auth_error"
    retryable = False


class ProviderPermissionError(ProviderError):
    """Provider denied access (403)."""

    public_message = "You don't have permission to perform that action on the external service."
    http_status = 403
    error_code = "provider_permission_denied"
    retryable = False


class ProviderValidationError(ProviderError):
    """Provider rejected the request due to bad input."""

    public_message = "The request to an external service was invalid."
    http_status = 400
    error_code = "provider_validation_error"
    retryable = False


# ─── Agent errors ─────────────────────────────────────────────────────────────


class AgentError(SeñoritaError):
    """Base for agent/orchestration errors."""

    public_message = "The AI agent encountered an error."
    error_code = "agent_error"


class AgentTimeoutError(AgentError):
    """Agent run exceeded AGENT_MAX_EXECUTION_TIME."""

    public_message = "That task took too long, so I stopped it safely."
    http_status = 504
    error_code = "agent_timeout"
    retryable = False


class AgentUsageLimitError(AgentError):
    """Per-user daily limit reached."""

    public_message = "Your daily AI usage limit has been reached."
    http_status = 429
    error_code = "usage_limit_exceeded"
    retryable = False


class AgentConfirmationExpiredError(AgentError):
    """Confirmation window has expired."""

    public_message = "That confirmation has expired. Please try again."
    http_status = 410
    error_code = "confirmation_expired"
    retryable = False


# ─── Human-readable error map for frontend ────────────────────────────────────

ERROR_CODE_MESSAGES: dict[str, str] = {
    "provider_auth_error": "Your connection to an external service needs to be renewed.",
    "provider_permission_denied": "You don't have permission to perform that action.",
    "provider_rate_limited": "We're being rate-limited. Please try again shortly.",
    "provider_timeout": "An external service timed out.",
    "provider_unavailable": "An external service is currently unavailable.",
    "provider_validation_error": "The request to an external service was invalid.",
    "agent_timeout": "That task took too long, so I stopped it safely.",
    "usage_limit_exceeded": "Your daily AI usage limit has been reached.",
    "confirmation_expired": "That confirmation has expired. Please try again.",
    "agent_error": "The AI agent encountered an error.",
    "internal_error": "An unexpected error occurred. Please try again.",
    "AUTHENTICATION_ERROR": "Your session is invalid. Please sign in again.",
    "PERMISSION_DENIED": "You don't have permission to do that.",
    "RATE_LIMITED": "Too many requests. Please slow down.",
    "CANCELLED": "The task was cancelled.",
}


def normalize_provider_error(exc: Exception, provider_name: str = "external service") -> ProviderError:
    """
    Map any SDK exception to a normalised ProviderError subclass.

    Adapters should call this in their except blocks.
    """
    msg = str(exc).lower()

    # HTTP status heuristics
    for code in ("401", "403", "429", "503", "504"):
        if code in msg:
            mapping = {
                "401": ProviderAuthenticationError,
                "403": ProviderPermissionError,
                "429": ProviderRateLimitError,
                "503": ProviderUnavailableError,
                "504": ProviderTimeoutError,
            }
            cls = mapping[code]
            return cls(
                detail=f"{provider_name}: {cls.public_message}",
                cause=exc,
            )

    if any(kw in msg for kw in ("timeout", "timed out", "deadline")):
        return ProviderTimeoutError(cause=exc)
    if any(kw in msg for kw in ("rate", "quota", "throttle")):
        return ProviderRateLimitError(cause=exc)
    if any(kw in msg for kw in ("unauthorized", "invalid_grant", "token")):
        return ProviderAuthenticationError(cause=exc)
    if any(kw in msg for kw in ("forbidden", "permission")):
        return ProviderPermissionError(cause=exc)
    if any(kw in msg for kw in ("503", "unavailable", "service error")):
        return ProviderUnavailableError(cause=exc)

    return ProviderError(
        detail=f"Unexpected error from {provider_name}.",
        cause=exc,
    )
