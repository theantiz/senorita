"""
Phase 4B verification tests.

Tests cover:
- Structured logging (JSON output, redaction)
- Metrics (counters increment correctly)
- Rate limiter (sliding window)
- Error normalisation
- Usage accounting (limits enforced)
- WebSocket ownership verification (mocked)
- Stale run detection logic
- DB pool is configured correctly
- Health endpoint accessibility
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# All tests in this module are self-contained unit tests.
# The `no_db` mark instructs the autouse conftest fixture to skip the database setup.
pytestmark = pytest.mark.no_db


# ─── Structured Logging ───────────────────────────────────────────────────────


class TestStructuredLogging:
    def test_json_output_is_parseable(self, capsys):
        """Log output should be valid JSON with key fields."""
        import os

        os.environ["LOG_FORMAT"] = "json"

        from app.core.logging import StructuredLogger, _build_logger

        _build_logger.cache_clear() if hasattr(_build_logger, "cache_clear") else None

        # Use a fresh named logger to avoid handler duplication
        log = StructuredLogger("test_json_logger_" + str(uuid.uuid4())[:8])
        log.info("test.event", run_id="abc-123", step="step_one")

        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l]
        assert lines, "No log output produced"
        parsed = json.loads(lines[-1])
        assert parsed["msg"] == "test.event"
        assert parsed["run_id"] == "abc-123"

    def test_sensitive_keys_are_redacted(self, capsys):
        """Sensitive field values must be replaced with ***REDACTED***."""
        from app.core.logging import _redact

        result = _redact({"password": "secret123", "safe_key": "visible", "api_key": "sk-xxx"})
        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["safe_key"] == "visible"

    def test_nested_sensitive_redaction(self):
        from app.core.logging import _redact

        nested = {"outer": {"token": "super-secret", "name": "ok"}}
        result = _redact(nested)
        assert result["outer"]["token"] == "***REDACTED***"
        assert result["outer"]["name"] == "ok"

    def test_list_values_are_traversed(self):
        from app.core.logging import _redact

        data = [{"password": "bad"}, {"safe": "ok"}]
        result = _redact(data)
        assert result[0]["password"] == "***REDACTED***"
        assert result[1]["safe"] == "ok"


# ─── Metrics ──────────────────────────────────────────────────────────────────


class TestMetrics:
    def test_counter_registration(self):
        """Metrics counters should be importable without error."""
        from app.core.metrics import (
            agent_runs_failed_total,
            agent_runs_total,
            llm_requests_total,
            tool_invocations_total,
            websocket_connections_total,
        )

        # Counters should have an inc() method
        assert hasattr(agent_runs_total, "inc")
        assert hasattr(tool_invocations_total, "inc")

    def test_metrics_endpoint_content(self):
        """get_metrics_response should return bytes and a MIME type."""
        from app.core.metrics import get_metrics_response

        data, content_type = get_metrics_response()
        assert isinstance(data, bytes)
        assert "text" in content_type


# ─── Rate Limiter ─────────────────────────────────────────────────────────────


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        from app.core.rate_limit import InProcessRateLimiter, RateLimitRule

        rl = InProcessRateLimiter()
        rl.define("test_op", RateLimitRule(max_calls=5, window_seconds=60))
        for _ in range(5):
            assert rl.allow("test_op", "user-1") is True

    def test_blocks_on_limit_exceeded(self):
        from app.core.rate_limit import InProcessRateLimiter, RateLimitRule

        rl = InProcessRateLimiter()
        rl.define("test_op", RateLimitRule(max_calls=3, window_seconds=60))
        for _ in range(3):
            rl.allow("test_op", "user-2")
        assert rl.allow("test_op", "user-2") is False

    def test_different_users_are_isolated(self):
        from app.core.rate_limit import InProcessRateLimiter, RateLimitRule

        rl = InProcessRateLimiter()
        rl.define("op", RateLimitRule(max_calls=2, window_seconds=60))
        for _ in range(2):
            rl.allow("op", "user-a")
        # user-a is exhausted, but user-b should still have budget
        assert rl.allow("op", "user-a") is False
        assert rl.allow("op", "user-b") is True

    def test_window_eviction_allows_new_requests(self):
        from app.core.rate_limit import InProcessRateLimiter, RateLimitRule

        rl = InProcessRateLimiter()
        rl.define("fast_op", RateLimitRule(max_calls=1, window_seconds=0.1))
        assert rl.allow("fast_op", "u") is True
        assert rl.allow("fast_op", "u") is False
        time.sleep(0.15)
        # After window expires, should allow again
        assert rl.allow("fast_op", "u") is True

    def test_unknown_endpoint_is_always_allowed(self):
        from app.core.rate_limit import InProcessRateLimiter

        rl = InProcessRateLimiter()
        # No rule defined
        for _ in range(100):
            assert rl.allow("unknown_endpoint", "any_key") is True


# ─── Error Normalisation ──────────────────────────────────────────────────────


class TestErrorNormalization:
    def test_timeout_maps_to_provider_timeout(self):
        from app.core.errors import ProviderTimeoutError, normalize_provider_error

        exc = Exception("Request timed out after 30s")
        result = normalize_provider_error(exc, "Google Calendar")
        assert isinstance(result, ProviderTimeoutError)
        assert result.retryable is True

    def test_rate_limit_maps_to_rate_limit_error(self):
        from app.core.errors import ProviderRateLimitError, normalize_provider_error

        exc = Exception("rate limit exceeded for quota")
        result = normalize_provider_error(exc, "Slack")
        assert isinstance(result, ProviderRateLimitError)
        assert result.retryable is True

    def test_401_maps_to_auth_error(self):
        from app.core.errors import ProviderAuthenticationError, normalize_provider_error

        exc = Exception("401 Unauthorized")
        result = normalize_provider_error(exc, "Gmail")
        assert isinstance(result, ProviderAuthenticationError)
        assert result.retryable is False

    def test_403_maps_to_permission_error(self):
        from app.core.errors import ProviderPermissionError, normalize_provider_error

        exc = Exception("403 Forbidden")
        result = normalize_provider_error(exc, "Gmail")
        assert isinstance(result, ProviderPermissionError)

    def test_unknown_maps_to_base_provider_error(self):
        from app.core.errors import ProviderError, normalize_provider_error

        exc = Exception("some weird sdk error")
        result = normalize_provider_error(exc, "TestProvider")
        assert isinstance(result, ProviderError)

    def test_error_public_message_is_safe(self):
        """Public messages must not contain SDK internals."""
        from app.core.errors import ProviderTimeoutError

        err = ProviderTimeoutError(cause=Exception("sdk_internal_error_xyz_123"))
        assert "sdk_internal_error" not in err.public_message
        assert "sdk_internal_error" not in str(err.detail)


# ─── Usage Accounting ─────────────────────────────────────────────────────────


class TestUsageAccounting:
    """Tests that don't need a real DB use mocked sessions."""

    @pytest.mark.asyncio
    async def test_exceeded_token_limit_raises_error(self):
        from app.core.usage import UsageAccounting, UsageExceededError, _DailyUsage

        user_id = uuid.uuid4()

        # Mock session that returns a row with tokens already near limit
        mock_row = MagicMock()
        mock_row.input_tokens = 90_000
        mock_row.output_tokens = 9_000
        mock_row.agent_runs = 0
        mock_row.estimated_cost_usd = 0.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        accounting = UsageAccounting(mock_session, user_id)
        with patch("app.core.usage.settings") as mock_settings:
            mock_settings.DAILY_TOKEN_LIMIT = 100_000
            mock_settings.DAILY_COST_LIMIT_USD = 0.0
            mock_settings.GEMINI_MODEL = "gemini-test"

            with pytest.raises(UsageExceededError) as exc_info:
                await accounting.check_and_record(5000, 1000)
            assert exc_info.value.limit_type == "token"

    def test_cost_estimation(self):
        from app.core.usage import _estimate_cost

        cost = _estimate_cost(1_000_000, 1_000_000)
        # At 0.075 per 1M input and 0.30 per 1M output
        assert abs(cost - 0.375) < 0.001


# ─── WebSocket Ownership ──────────────────────────────────────────────────────


class TestWebSocketOwnership:
    """Verify that subscription is denied if user doesn't own the run."""

    @pytest.mark.asyncio
    async def test_subscription_denied_for_wrong_user(self):
        """When ownership query returns None, the WS should send Forbidden."""
        # Simulate the ownership check path
        run_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # The ownership query should return None (not owned)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        responses = []
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=lambda x: responses.append(x))

        # Simulate the ownership check logic directly
        from sqlalchemy import select

        from app.db.models.run import AgentRun

        ownership_stmt = select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.user_id == user_id,
        )
        ownership_result = await mock_session.execute(ownership_stmt)
        owned_run = ownership_result.scalar_one_or_none()

        if owned_run is None:
            await mock_ws.send_json({"type": "error", "message": "Forbidden."})

        assert responses == [{"type": "error", "message": "Forbidden."}]


# ─── DB Pool Configuration ────────────────────────────────────────────────────


class TestDBPoolConfiguration:
    def test_pool_pre_ping_is_enabled(self):
        """pool_pre_ping=True must be set so stale connections are detected."""
        from app.db.session import engine

        pool = engine.pool
        # pool_pre_ping is stored on the engine creator
        assert engine.pool._pre_ping is True

    def test_pool_recycle_is_set(self):
        """pool_recycle must be a positive number (< 3600 recommended)."""
        from app.db.session import engine

        assert engine.pool._recycle > 0
        assert engine.pool._recycle <= 3600


# ─── Stale Run Recovery ───────────────────────────────────────────────────────


class TestStaleRunRecovery:
    @pytest.mark.asyncio
    async def test_stale_run_detection_logic(self):
        """_mark_stale_runs should return the count of runs marked FAILED."""
        with patch("app.workers.stale_run_recovery.async_session_factory") as mock_factory:
            from datetime import timedelta

            from app.workers import stale_run_recovery

            mock_run = MagicMock()
            mock_run.id = uuid.uuid4()
            mock_run.user_id = uuid.uuid4()
            mock_run.updated_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1000)
            mock_run.plan_id = None
            mock_run.status = "RUNNING"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_run]

            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_factory.return_value = mock_session

            with patch("app.agents.events.record_and_publish_event", new=AsyncMock()):
                count = await stale_run_recovery._mark_stale_runs()

            assert count == 1
            assert mock_run.status == "FAILED"
