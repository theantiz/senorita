from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class ToolMetrics:
    calls_total: Counter[str] = field(default_factory=Counter)
    success_total: Counter[str] = field(default_factory=Counter)
    failure_total: Counter[str] = field(default_factory=Counter)
    retry_total: Counter[str] = field(default_factory=Counter)
    latency_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def record(self, tool_name: str, *, success: bool, duration_ms: float, retries: int = 0) -> None:
        self.calls_total[tool_name] += 1
        if success:
            self.success_total[tool_name] += 1
        else:
            self.failure_total[tool_name] += 1
        self.retry_total[tool_name] += retries
        self.latency_ms[tool_name].append(duration_ms)

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        tools = set(self.calls_total) | set(self.success_total) | set(self.failure_total)
        return {tool: self._snapshot_tool(tool) for tool in sorted(tools)}

    def _snapshot_tool(self, tool_name: str) -> dict[str, float | int]:
        latencies = self.latency_ms.get(tool_name, [])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return {
            "calls_total": self.calls_total[tool_name],
            "success_total": self.success_total[tool_name],
            "failure_total": self.failure_total[tool_name],
            "retry_total": self.retry_total[tool_name],
            "avg_latency_ms": round(avg_latency, 2),
        }
