from __future__ import annotations
from typing import TYPE_CHECKING

from app.agents.tool_system.dependency_graph import ToolDependencyGraph
from app.agents.tool_system.registry import ToolRegistry

if TYPE_CHECKING:
    from app.agents.schemas import IntentSchema

class ToolPlanner:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.graph = ToolDependencyGraph(registry)

    def discover(self, message: str, *, intent: "IntentSchema | None" = None, limit: int = 12) -> list[str]:
        categories = None
        search_query = message
        
        if intent:
            categories = intent.required_capabilities if intent.required_capabilities else None
            # Combine intent terms into the search query for better matching
            search_query = f"{message} {intent.intent} {' '.join(intent.required_capabilities)}"
            
        definitions = self.registry.search(search_query, categories=categories, limit=limit)
        expanded = self.graph.expand([definition.name for definition in definitions])
        return expanded[:limit]
