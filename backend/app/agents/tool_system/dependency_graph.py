from __future__ import annotations

from app.agents.tool_system.registry import ToolRegistry


class ToolDependencyGraph:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def dependencies_for(self, tool_name: str) -> list[str]:
        definition = self.registry.get(tool_name)
        if not definition:
            return []
        return list(definition.dependencies)

    def expand(self, tool_names: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(name: str) -> None:
            if name in seen:
                return
            seen.add(name)
            for dependency in self.dependencies_for(name):
                visit(dependency)
            if self.registry.get(name):
                ordered.append(name)

        for tool_name in tool_names:
            visit(tool_name)

        return ordered
