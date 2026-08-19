# Tool Architecture

The tool system is split across `backend/app/agents/tool_system/`:

- `definitions.py`: tool metadata, risk levels, permissions, retry policy
- `registry.py`: registration, inventory, search
- `executor.py`: validation, permission checks, confirmation, timeout, retries, logging, result normalization
- `context.py`: per-call user/request context
- `permissions.py`: feature flags and confirmation policy
- `confirmation.py`: confirmation-required result generation
- `validation.py`: strict argument checks
- `dependency_graph.py`: dependency expansion
- `planner.py`: dynamic tool discovery
- `metrics.py`: in-process call counters and latency snapshots
- `rate_limit.py`: in-memory per-user/per-tool rate limiting

Existing Gemini callable functions remain in `tool_registry.py` for backward compatibility. Their handlers are registered with metadata and are executed only through `ToolExecutor`.

The orchestrator calls `discover_tools_for_message()` before each model request and passes only the selected functions to Gemini. If discovery returns nothing, it falls back to a small compatibility set.
