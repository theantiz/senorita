from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agents.tool_system.definitions import ToolDefinition

ToolHandler = Callable[..., Any]


class ToolRegistry:
    def __init__(self):
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def get(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def handler_for(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def all(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def enabled(self) -> list[ToolDefinition]:
        return [definition for definition in self._definitions.values() if definition.enabled]

    def categories(self) -> list[str]:
        return sorted({definition.category for definition in self._definitions.values()})

    def inventory(self) -> list[dict[str, Any]]:
        return [
            definition.to_inventory_row()
            for definition in sorted(self._definitions.values(), key=lambda item: item.name)
        ]

    def search(
        self,
        query: str,
        *,
        categories: list[str] | None = None,
        limit: int = 8,
    ) -> list[ToolDefinition]:
        terms = {term for term in query.replace("_", " ").lower().split() if len(term) > 2}
        category_filter = {category.lower() for category in categories or []}
        scored: list[tuple[int, ToolDefinition]] = []

        for definition in self.enabled():
            if category_filter and definition.category.lower() not in category_filter:
                continue
            text = definition.searchable_text()
            score = sum(3 for term in terms if term in definition.name.replace("_", " ").lower())
            score += sum(1 for term in terms if term in text)
            score += 1 if not terms else 0
            if score > 0:
                scored.append((score, definition))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [definition for _, definition in scored[:limit]]
