from __future__ import annotations

from app.agents.tool_system.dependency_graph import ToolDependencyGraph
from app.agents.tool_system.registry import ToolRegistry


class ToolPlanner:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.graph = ToolDependencyGraph(registry)

    def discover(self, message: str, *, limit: int = 12) -> list[str]:
        definitions = self.registry.search(message, limit=limit)
        expanded = self.graph.expand([definition.name for definition in definitions])
        return expanded[:limit]
