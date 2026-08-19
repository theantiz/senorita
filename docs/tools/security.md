# Tool Security

Security rules enforced by the current implementation:

- All database handlers receive `user_id` and filter resources by owner.
- Tool arguments are validated centrally before execution.
- Unknown arguments are rejected.
- High-risk sends and deletes create durable confirmations and return `confirmation_required`.
- Confirmation approval is tied to the original tool invocation and reuses the stored argument snapshot.
- Tool invocation persistence stores argument hashes and redacted argument snapshots; secret-like fields are not stored raw.
- Side-effect retries can use durable idempotency keys.
- Provider errors are logged server-side and returned as normalized, non-stack-trace errors.
- External content from email, Slack, web, documents, and repositories is treated as untrusted in prompts.
- Local OS tools do not expose arbitrary shell execution.
- Process listing avoids command-line arguments to reduce accidental secret exposure.

Known gaps:

- Rate limiting and metrics are in-process and reset on restart.
