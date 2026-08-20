"""
Application metrics for Señorita.

Uses a simple in-process counter/histogram approach that exposes a
Prometheus-compatible /metrics endpoint. No external dependencies beyond
the standard library + prometheus_client (already in requirements).

If prometheus_client is not available, metrics are silently no-ops so the
app still runs in minimal environments.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Lazy import so the app works even without prometheus_client installed
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False

    class _Noop:
        """No-op metric that accepts any call."""

        def labels(self, **_):
            return self

        def inc(self, *_, **__):
            pass

        def dec(self, *_, **__):
            pass

        def observe(self, *_, **__):
            pass

        def set(self, *_, **__):
            pass

    def Counter(*_, **__):
        return _Noop()  # type: ignore[misc]

    def Gauge(*_, **__):
        return _Noop()  # type: ignore[misc]

    def Histogram(*_, **__):
        return _Noop()  # type: ignore[misc]

    def generate_latest():
        return b""  # type: ignore[misc]

    CONTENT_TYPE_LATEST = "text/plain"  # type: ignore[assignment]


# ─── Agent Runs ───────────────────────────────────────────────────────────────
agent_runs_total = Counter(
    "agent_runs_total",
    "Total agent runs created",
    ["routing"],  # direct | plan
)
agent_runs_success_total = Counter(
    "agent_runs_success_total",
    "Agent runs that completed successfully",
)
agent_runs_failed_total = Counter(
    "agent_runs_failed_total",
    "Agent runs that failed",
    ["reason"],  # timeout | exception | validation
)
agent_runs_cancelled_total = Counter(
    "agent_runs_cancelled_total",
    "Agent runs explicitly cancelled",
)
agent_run_duration_seconds = Histogram(
    "agent_run_duration_seconds",
    "End-to-end duration of an agent run",
    buckets=[1, 5, 15, 30, 60, 120, 300, 600],
)

# ─── Plans ────────────────────────────────────────────────────────────────────
agent_plan_total = Counter("agent_plan_total", "Total plans created")
agent_plan_success_total = Counter("agent_plan_success_total", "Plans completed successfully")
agent_plan_failed_total = Counter("agent_plan_failed_total", "Plans that failed")

# ─── Steps ────────────────────────────────────────────────────────────────────
agent_step_total = Counter("agent_step_total", "Total plan steps executed", ["tool_name"])
agent_step_failed_total = Counter("agent_step_failed_total", "Plan steps that failed", ["tool_name"])

# ─── Tool invocations ─────────────────────────────────────────────────────────
tool_invocations_total = Counter(
    "tool_invocations_total",
    "Total tool calls",
    ["tool_name", "risk_level"],
)
tool_invocation_failures_total = Counter(
    "tool_invocation_failures_total",
    "Tool calls that failed",
    ["tool_name", "error_code"],
)
tool_invocation_duration_seconds = Histogram(
    "tool_invocation_duration_seconds",
    "Duration of individual tool calls",
    ["tool_name"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60],
)

# ─── Confirmations ────────────────────────────────────────────────────────────
confirmation_requests_total = Counter("confirmation_requests_total", "Confirmations requested")
confirmation_approved_total = Counter("confirmation_approved_total", "Confirmations approved")
confirmation_rejected_total = Counter("confirmation_rejected_total", "Confirmations rejected")
confirmation_expired_total = Counter("confirmation_expired_total", "Confirmations expired")

# ─── WebSocket ────────────────────────────────────────────────────────────────
websocket_connections_total = Counter("websocket_connections_total", "Total WS connections accepted")
websocket_active_connections = Gauge("websocket_active_connections", "Currently open WS connections")
websocket_disconnects_total = Counter("websocket_disconnects_total", "WS connections closed")
websocket_reconnects_total = Counter("websocket_reconnects_total", "WS reconnect subscribe events")
websocket_auth_failures_total = Counter("websocket_auth_failures_total", "WS connections rejected for auth")

# ─── Events ───────────────────────────────────────────────────────────────────
agent_event_published_total = Counter("agent_event_published_total", "Events persisted and broadcast")
agent_event_replayed_total = Counter("agent_event_replayed_total", "Events replayed to reconnecting clients")
agent_event_delivery_latency_seconds = Histogram(
    "agent_event_delivery_latency_seconds",
    "Latency from event creation to WebSocket delivery",
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5],
)

# ─── LLM ──────────────────────────────────────────────────────────────────────
llm_requests_total = Counter(
    "llm_requests_total",
    "Total calls to LLM provider",
    ["provider", "model"],
)
llm_requests_failed_total = Counter(
    "llm_requests_failed_total",
    "Failed calls to LLM provider",
    ["provider", "model", "error_type"],
)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "Duration of LLM API calls",
    ["provider", "model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)
llm_input_tokens_total = Counter(
    "llm_input_tokens_total",
    "Total LLM input tokens consumed",
    ["provider", "model"],
)
llm_output_tokens_total = Counter(
    "llm_output_tokens_total",
    "Total LLM output tokens produced",
    ["provider", "model"],
)

# ─── Memory ───────────────────────────────────────────────────────────────────
memory_search_total = Counter("memory_search_total", "Memory semantic searches performed")
memory_search_duration_seconds = Histogram(
    "memory_search_duration_seconds",
    "Duration of memory vector searches",
    buckets=[0.05, 0.1, 0.5, 1, 5],
)

# ─── Database ─────────────────────────────────────────────────────────────────
db_pool_checked_out = Gauge("db_pool_checked_out", "DB connections currently checked out")


@asynccontextmanager
async def timed_llm_request(provider: str, model: str) -> AsyncIterator[None]:
    """Context manager that records LLM call duration and increments counters."""
    llm_requests_total.labels(provider=provider, model=model).inc()
    t0 = time.perf_counter()
    try:
        yield
        llm_request_duration_seconds.labels(provider=provider, model=model).observe(time.perf_counter() - t0)
    except Exception as exc:
        llm_requests_failed_total.labels(provider=provider, model=model, error_type=type(exc).__name__).inc()
        raise


def get_metrics_response() -> tuple[bytes, str]:
    """Return raw Prometheus scrape payload."""
    return generate_latest(), CONTENT_TYPE_LATEST


# --- Phase 5 Metrics ---
voice_requests_total = Counter("senorita_voice_requests_total", "Voice STT requests")
voice_failures_total = Counter("senorita_voice_failures_total", "Voice processing failures")
voice_latency = Histogram("senorita_voice_latency_seconds", "Voice E2E latency")
memory_retrieval_total = Counter("senorita_memory_retrieval_total", "Memory searches")
memory_updates_total = Counter("senorita_memory_updates_total", "Memory updates")
memory_supersessions_total = Counter("senorita_memory_supersessions_total", "Memory supersessions")
proactive_notifications_total = Counter("senorita_proactive_notifications_total", "Proactive notifications sent")
proactive_duplicates_total = Counter("senorita_proactive_duplicates_total", "Proactive notifications deduplicated")
workflow_execution_total = Counter("senorita_workflow_execution_total", "Workflows executed")

context_build_total = Counter("senorita_context_build_total", "Context Builder runs")
context_build_failures_total = Counter("senorita_context_build_failures_total", "Context Builder failures")
context_build_latency = Histogram("senorita_context_build_latency_seconds", "Context Builder latency")
context_items_selected_total = Counter("senorita_context_items_selected_total", "Context items selected")
context_items_dropped_total = Counter("senorita_context_items_dropped_total", "Context items dropped")
context_token_estimate = Histogram("senorita_context_token_estimate", "Context Token estimate")
preference_retrieval_total = Counter("senorita_preference_retrieval_total", "Preferences retrieved")
preference_updates_total = Counter("senorita_preference_updates_total", "Preferences updated")
preference_supersessions_total = Counter("senorita_preference_supersessions_total", "Preferences superseded")
memory_expiration_total = Counter("senorita_memory_expiration_total", "Memories expired dynamically")

context_vector_search_total = Counter("senorita_context_vector_search_total", "Vector searches for context")
context_vector_search_failures_total = Counter(
    "senorita_context_vector_search_failures_total", "Vector search failures"
)
context_memories_selected_total = Counter("senorita_context_memories_selected_total", "Memories selected")
context_preferences_selected_total = Counter("senorita_context_preferences_selected_total", "Preferences selected")
context_similarity_histogram = Histogram("senorita_context_similarity", "Vector similarity score distribution")
preference_created_total = Counter("senorita_preference_created_total", "Preferences created")
preference_updated_total = Counter("senorita_preference_updated_total", "Preferences updated")
preference_superseded_total = Counter("senorita_preference_superseded_total", "Preferences superseded via conflict")
preference_conflicts_total = Counter("senorita_preference_conflicts_total", "Preferences in conflict")
context_relevance_failures_total = Counter(
    "senorita_context_relevance_failures_total", "Context relevance checks failed"
)
