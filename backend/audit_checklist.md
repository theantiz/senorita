IMPLEMENTED:
- Intent schema and extraction
- Tool planner and schema validation
- AgentPlan and AgentPlanStep DB models
- Plan validation (cycles, safety)
- Phase 2 ToolExecutor security boundary (permissions, risk, confirmation)
- Simple WebSocket endpoint (/stream)
- Direct vs Complex routing

PARTIALLY IMPLEMENTED:
- PlanExecutor (Runs sequentially/parallel, but executes inside HTTP/WS request thread instead of background)
- Event schema (Only pushes raw strings via progress_callback)
- Error handling (Returns raw errors)

MISSING:
- WebSocket Authentication
- AgentRun and AgentRunEvent persistence models
- Decoupled background execution (BackgroundTasks)
- Reconnection and event replay (last_event_id)
- User-facing safe messages (hiding tool names)
- Heartbeat implementation
- Disconnect-safe execution
- Comprehensive test suite for WS & Runs

UNSAFE:
- Execution lifetime is bound to WebSocket connection (disconnect cancels/halts the Python task immediately)
- progress_callback pushes directly to websocket without persisting, meaning missed events are lost forever.
- No WS authentication.

UNTESTED:
- WebSocket load and concurrency
- State recovery
