# Tool Integrations

Current providers:

- `database`: local Postgres-backed Senorita data
- `gmail`: Gmail indexed data plus live summarize/draft/send through Gmail APIs
- `slack`: Slack indexed data plus live send through Slack Web API
- `web`: Google News RSS and Gemini Google Search grounding
- `documents`: uploaded document records and vector chunks
- `local`: host system and repository inspection

Provider health is currently represented through tool metadata and `integration_status`. Gmail and Slack connection status is read from the `integrations` table.

Future provider abstraction work should move Gmail and Slack SDK calls behind interfaces such as `EmailProvider` and `MessagingProvider`, keeping handlers focused on validation and result shaping.
