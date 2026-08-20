# Señorita AI — Production Configuration

This document lists all environment variables required or supported in a production deployment.

## Core Application
* `HOST`: Bind address (default: `127.0.0.1`, use `0.0.0.0` in Docker)
* `PORT`: Bind port (default: `8000`)
* `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g. `https://senorita.app`)
* `SECRET_KEY`: Random string for generic crypto/signatures (Required)
* `ENCRYPTION_KEY`: Base64 Fernet key used to encrypt OAuth tokens (Required)
* `LOG_LEVEL`: Application log level (default: `INFO`)
* `LOG_FORMAT`: Set to `json` for structured logging, or `text` for local development.

## Database
* `DATABASE_URL`: SQLAlchemy-compatible async connection string (e.g. `postgresql+asyncpg://user:pass@host:5432/db`)

## AI Providers
* `GEMINI_API_KEY`: API key for Google Gemini (Required)
* `GEMINI_MODEL`: LLM to use (default: `gemini-3.1-flash-lite`)
* `EMBEDDING_MODEL`: Vector embedding model (default: `gemini-embedding-001`)

## Cost Control & Rate Limiting
* `DAILY_TOKEN_LIMIT`: Maximum LLM tokens a user can consume per day (default: `0` / unlimited)
* `DAILY_COST_LIMIT_USD`: Maximum estimated cost per user per day in USD (default: `0.0` / unlimited)
* `DAILY_AGENT_RUN_LIMIT`: Maximum number of agent runs per user per day (default: `0` / unlimited)

## Stability & Background Tasks
* `STALE_RUN_TIMEOUT_SECONDS`: Time before a silent RUNNING task is marked FAILED (default: `900` / 15m)
* `STALE_RUN_CHECK_INTERVAL_SECONDS`: How often the stale recovery worker runs (default: `120`)
* `AGENT_MAX_EXECUTION_TIME`: Hard timeout for agent direct execution (default: `600`)

## Integrations (Optional)
* `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`: OAuth credentials for Gmail integration
* `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET`: OAuth credentials for Slack integration
* `SLACK_SIGNING_SECRET`: Secret to verify incoming Slack webhooks
