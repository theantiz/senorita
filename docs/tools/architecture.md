# Tool Architecture

The tool system is split across `backend/app/agents/tool_system/`:

- `definitions.py`: tool metadata, risk levels, permissions, retry policy
- `registry.py`: registration, inventory, search
- `executor.py`: validation, permission checks, confirmation, timeout, retries, logging, result normalization
- `context.py`: per-call user/request context
- `permissions.py`: feature flags and confirmation policy
- `confirmation.py`: confirmation-required result generation
- `persistence.py`: durable invocation, confirmation, idempotency, and argument redaction helpers
- `validation.py`: strict argument checks
- `dependency_graph.py`: dependency expansion
- `planner.py`: dynamic tool discovery
- `metrics.py`: in-process call counters and latency snapshots
- `rate_limit.py`: in-memory per-user/per-tool rate limiting

Existing Gemini callable functions remain in `tool_registry.py` for backward compatibility. Their handlers are registered with metadata and are executed only through `ToolExecutor`.

The orchestrator calls `discover_tools_for_message()` before each model request and passes only the selected functions to Gemini. If discovery returns nothing, it falls back to a small compatibility set.

Production executions with a database session create `tool_invocations` rows. High-risk tools create `tool_confirmations` rows and return a confirmation ID; approval replays the stored invocation arguments instead of accepting new arguments. Side-effecting tools can also use a durable `idempotency_key` so request retries return the original result.

Provider-specific API work is kept behind integration provider interfaces such as `EmailProvider` and `MessagingProvider`. Tool handlers should use those interfaces instead of constructing provider SDK clients directly.
