# Tool Security

Security rules enforced by the current implementation:

- All database handlers receive `user_id` and filter resources by owner.
- Tool arguments are validated centrally before execution.
- Unknown arguments are rejected.
- High-risk sends and deletes return `confirmation_required`.
- Provider errors are logged server-side and returned as normalized, non-stack-trace errors.
- External content from email, Slack, web, documents, and repositories is treated as untrusted in prompts.
- Local OS tools do not expose arbitrary shell execution.
- Process listing avoids command-line arguments to reduce accidental secret exposure.

Known gaps:

- Confirmation state is not yet persisted across conversations.
- Rate limiting and metrics are in-process and reset on restart.
- Some provider operations still use direct Gmail/Slack SDK calls instead of provider interface classes.
