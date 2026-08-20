"""
In-process rate limiter for HTTP endpoints and WebSocket connections.

Uses a sliding window algorithm (token bucket style) keyed by
(user_id | ip_address, endpoint). Because Señorita is currently
single-process, this is acceptable without Redis.

LIMITATION: This limiter is NOT shared across processes.
If you scale to multiple workers, replace with a Redis-backed limiter
(e.g. slowapi + Redis store, or a custom lua script).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class RateLimitRule:
    """A rate limit rule: at most `max_calls` in `window_seconds`."""
    max_calls: int
    window_seconds: float


class InProcessRateLimiter:
    """
    Thread-safe (GIL-protected) sliding window rate limiter.

    Example rules:
        limiter.define("chat_message", RateLimitRule(30, 60))      # 30/min
        limiter.define("websocket_connect", RateLimitRule(10, 60)) # 10 new WS/min
        limiter.define("agent_run_create", RateLimitRule(20, 60))  # 20 runs/min
        limiter.define("confirmation_attempt", RateLimitRule(5, 60)) # 5 attempts/min
    """

    def __init__(self) -> None:
        # key → deque of monotonic timestamps
        self._calls: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._rules: Dict[str, RateLimitRule] = {}

    def define(self, name: str, rule: RateLimitRule) -> None:
        self._rules[name] = rule

    def allow(self, endpoint: str, key: str) -> bool:
        """
        Return True if the request is allowed, False if rate-limited.

        Args:
            endpoint: one of the defined rule names.
            key: opaque user/ip string (never used as log or metric label).
        """
        rule = self._rules.get(endpoint)
        if rule is None:
            return True  # Unknown endpoints are not limited

        bucket_key = (endpoint, key)
        now = time.monotonic()
        window = self._calls[bucket_key]

        # Evict timestamps outside the window
        cutoff = now - rule.window_seconds
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= rule.max_calls:
            return False

        window.append(now)
        return True

    def remaining(self, endpoint: str, key: str) -> int:
        """How many calls remain in the current window."""
        rule = self._rules.get(endpoint)
        if rule is None:
            return 999
        bucket_key = (endpoint, key)
        now = time.monotonic()
        window = self._calls[bucket_key]
        cutoff = now - rule.window_seconds
        count = sum(1 for t in window if t >= cutoff)
        return max(0, rule.max_calls - count)


# ─── Singleton ────────────────────────────────────────────────────────────────

limiter = InProcessRateLimiter()

# Default rules — override via environment if needed
limiter.define("chat_message",          RateLimitRule(60, 60))   # 60/min per user
limiter.define("websocket_connect",     RateLimitRule(15, 60))   # 15 new WS/min per user
limiter.define("agent_run_create",      RateLimitRule(20, 60))   # 20 runs/min per user
limiter.define("plan_create",           RateLimitRule(10, 60))   # 10 plans/min per user
limiter.define("confirmation_attempt",  RateLimitRule(10, 60))   # 10 confirmations/min per user
limiter.define("tool_execution",        RateLimitRule(100, 60))  # 100 tool calls/min per user
