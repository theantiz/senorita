from app.agents.schemas import PlanSchema
from app.agents.tool_registry import get_tool_registry


class PlanValidationError(Exception):
    """Raised when a plan fails validation."""

    pass


def validate_plan(plan: PlanSchema) -> None:  # noqa: C901
    """
    Validates a generated plan for safety and structural correctness:
    - Schema & format correctness.
    - All tools must exist in the registry.
    - Step dependency targets must exist.
    - Graph structure must be a valid Directed Acyclic Graph (DAG) with no cycles.
    - Execution modes and risk levels must match allowed values.
    """
    registry = get_tool_registry()
    step_ids = {step.step_id for step in plan.steps}

    # 1. format and limits check
    if len(plan.steps) == 0:
        raise PlanValidationError("Plan must contain at least one step.")

    # 2. Tool existence, execution mode, and risk level checks
    for step in plan.steps:
        # Validate tool existence
        tool_definition = registry.get(step.tool_name)
        if not tool_definition:
            raise PlanValidationError(f"Step '{step.step_id}' references non-existent tool '{step.tool_name}'.")

        # Validate execution mode
        if step.execution_mode not in ("sequential", "parallel"):
            raise PlanValidationError(
                f"Step '{step.step_id}' has invalid execution_mode '{step.execution_mode}'. Must be 'sequential' or 'parallel'."
            )

        # Validate risk level
        if step.risk_level not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise PlanValidationError(f"Step '{step.step_id}' has invalid risk_level '{step.risk_level}'.")

        # 3. Dependency validation
        for dep in step.depends_on:
            if dep not in step_ids:
                raise PlanValidationError(f"Step '{step.step_id}' depends on non-existent step_id '{dep}'.")
            if dep == step.step_id:
                raise PlanValidationError(f"Step '{step.step_id}' cannot depend on itself.")

    # 4. DAG Cycle Detection (DFS)
    visited = {}  # step_id -> status (0 = unvisited, 1 = visiting, 2 = visited)
    for step_id in step_ids:
        visited[step_id] = 0

    # Build adjacency list: node -> dependencies
    adj_list = {step.step_id: step.depends_on for step in plan.steps}

    def has_cycle(node: str) -> bool:
        visited[node] = 1  # visiting
        for dep in adj_list.get(node, []):
            if visited[dep] == 1:
                return True  # Found cycle back to visiting node
            elif visited[dep] == 0:
                if has_cycle(dep):
                    return True
        visited[node] = 2  # visited
        return False

    for step_id in step_ids:
        if visited[step_id] == 0:
            if has_cycle(step_id):
                raise PlanValidationError("Plan contains a circular dependency (not a valid DAG).")
