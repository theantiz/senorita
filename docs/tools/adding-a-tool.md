# Adding A Tool

Adding a backend tool should not require changing the orchestrator.

1. Add a Gemini callable schema function in `backend/app/agents/tool_registry.py`.
2. Add an async handler named `_handle_<tool_name>`.
3. Add a `ToolDefinition` entry to `TOOL_DEFINITIONS`.
4. Register the handler in `_handler_map()`.
5. Add tests for validation, permissions, and result shape.
6. Add or update docs if the tool introduces a new provider or risk model.
7. For provider-backed tools, add or reuse a provider interface instead of calling SDKs directly from the handler.
8. For side-effecting tools, support `idempotency_key` through the executor and mark `side_effects` accurately.

Handlers should:

- Accept `(session, user_id, **arguments)`.
- Validate resource ownership before reading or writing.
- Return dictionaries, not FastAPI responses.
- Return `{"error": "message"}` for expected user-facing failures.
- Log provider/internal details server-side instead of returning stack traces.
- Never accept confirmation IDs as permission to run new arguments; approvals must execute the stored invocation.

Use `ToolPermission`, `RiskLevel`, and `ConfirmationPolicy` honestly. Sending, deleting, or external side effects should be high risk unless there is a very clear reason otherwise.
