from __future__ import annotations

import time
from collections import defaultdict, deque
from uuid import UUID

from app.agents.tool_system.definitions import ToolDefinition


class InMemoryRateLimiter:
    def __init__(self):
        self._calls: dict[tuple[UUID, str], deque[float]] = defaultdict(deque)

    def allow(self, user_id: UUID, definition: ToolDefinition) -> bool:
        limit = definition.rate_limit_per_minute
        if not limit:
            return True

        key = (user_id, definition.name)
        now = time.monotonic()
        window = self._calls[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True
