# Adding A Tool

Adding a backend tool should not require changing the orchestrator.

1. Add a Gemini callable schema function in `backend/app/agents/tool_registry.py`.
2. Add an async handler named `_handle_<tool_name>`.
3. Add a `ToolDefinition` entry to `TOOL_DEFINITIONS`.
4. Register the handler in `_handler_map()`.
5. Add tests for validation, permissions, and result shape.
6. Add or update docs if the tool introduces a new provider or risk model.

Handlers should:

- Accept `(session, user_id, **arguments)`.
- Validate resource ownership before reading or writing.
- Return dictionaries, not FastAPI responses.
- Return `{"error": "message"}` for expected user-facing failures.
- Log provider/internal details server-side instead of returning stack traces.

Use `ToolPermission`, `RiskLevel`, and `ConfirmationPolicy` honestly. Sending, deleting, or external side effects should be high risk unless there is a very clear reason otherwise.
