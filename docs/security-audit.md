# Señorita AI — Security Audit & Hardening Report

**Phase 4B Completion**

## 1. Authentication & Authorization
* **WebSocket Ownership Checks**: Verified. Subscriptions via WebSocket now strictly enforce that the `user_id` on the `AgentRun` matches the authenticated `current_user`. A user cannot subscribe to another user's event stream.
* **HTTP Auth**: API endpoints remain secured by Bearer token matching the SHA-256 hash in `AuthToken`.
* **Token Redaction**: The new structured JSON logger recursively filters `token`, `password`, `secret`, `api_key`, etc., emitting `***REDACTED***` in their place.
* **Stale Token Eviction**: Configured in APScheduler via `refresh_expired_tokens` worker.

## 2. Network Security & Headers
* **Security Headers**: Added global middleware setting `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`. HTTP Strict Transport Security (HSTS) is enabled when the request scheme is HTTPS and not in `TESTING` mode.
* **CORS**: Strongly typed via `CORS_ORIGINS` environment variable (no wildcard in prod).

## 3. Denial of Service (DoS) Protections
* **HTTP Rate Limiting**: Implemented a sliding window token bucket rate limiter in memory (due to single-node constraint). Limits chat, WS connections, and agent run creations per user.
* **Payload Limits**: Added a strict 64KB max payload check to incoming WebSocket messages to prevent memory flooding. Upload limits (Voice API) capped at 8MB.
* **Database Connection Pool**: Tuned SQLAlchemy pool (`pool_size=5`, `max_overflow=10`, `pool_timeout=30s`). `pool_pre_ping=True` ensures the server drops stale sockets gracefully.

## 4. Cost Control & LLM Abuse Protection
* **Per-User Quotas**: Introduced `daily_usage` table. System tracks input/output tokens and prevents execution if limits (`DAILY_TOKEN_LIMIT`, `DAILY_COST_LIMIT_USD`) are exceeded.
* **Provider Error Normalization**: External errors (500s, Rate limits) are caught, sanitized into `ProviderError`, and safely delivered to the UI without exposing internal SDK stack traces.
* **Stale Run Recovery**: A background worker now marks abandoned `RUNNING` agent plans as `FAILED` if they haven't sent a heartbeat, preventing infinite loop/zombie processes.

## 5. Deployment / CI Hardening
* **Container Health Checks**: `HEALTHCHECK` instructions added to backend Dockerfile, utilizing the new `/health/live` endpoint.
* **Non-Root User**: The backend Docker container now drops privileges to the `senorita` user.
* **CI/CD Separation**: The CI pipeline was expanded to include separate linting (Ruff), type checking (TypeScript), and unit test jobs, reducing deployment risk.
