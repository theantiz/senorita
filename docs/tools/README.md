# Senorita Tool System

The backend tool system gives the AI assistant a controlled way to inspect and act on user data. Tools are now registered through metadata, executed through a central executor, and exposed through discovery instead of loading every capability for every request.

## Current Inventory

The live inventory is available in code through `get_tool_inventory()` and over the API at `GET /api/v1/tools`.

Implemented categories:

- `productivity`: tasks and reminders
- `calendar`: local and synced calendar reads plus local event creation
- `communication`: contacts, Gmail index, Slack index, drafts and sends
- `memory`: personal memory search and management
- `research`: web/news/document tools
- `developer`: repository analysis
- `system`: local app/system inspection
- `orchestration`: daily brief and cross-channel follow-up helpers
- `admin`: tool and integration status

## Important Limits

The system does not provide unrestricted shell execution. Destructive and sending tools are marked high risk and require confirmation through the executor.
