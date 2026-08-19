# Tool Permissions

Tools declare permissions using `ToolPermission`:

- `READ`
- `WRITE`
- `SEND`
- `DELETE`
- `SYSTEM`
- `MEMORY`
- `COMMUNICATION`
- `RESEARCH`
- `DOCUMENT`
- `DEVELOPER`
- `ADMIN`

Tools also declare a risk level: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.

Confirmation policies:

- `always_allow`
- `ask_once`
- `ask_each_time`
- `never_allow`

High-risk send/delete operations require confirmation unless an internal caller passes a confirmed execution request. API execution supports this with `confirmed: true`; normal model tool calls do not silently bypass confirmation.

Feature flags can disable tool groups:

- `ENABLE_GMAIL_TOOLS=false`
- `ENABLE_SLACK_TOOLS=false`
- `ENABLE_WEB_TOOLS=false`
- `ENABLE_SYSTEM_TOOLS=false`
- `ENABLE_RESEARCH_TOOLS=false`
