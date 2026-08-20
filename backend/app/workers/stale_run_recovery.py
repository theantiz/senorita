"""
Stale AgentRun detector and recovery.

Runs on startup as a background task. Periodically scans for AgentRun
records that have been in RUNNING state without an updated_at heartbeat
for longer than STALE_RUN_TIMEOUT_SECONDS. Marks them FAILED so they do
not sit in RUNNING forever after a process crash.

Phase 2 idempotency prevents duplicate side effects on any retry.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_factory

log = get_logger(__name__)

# Configurable via env: STALE_RUN_TIMEOUT_SECONDS (default: 15 minutes)
_STALE_TIMEOUT = int(getattr(settings, "STALE_RUN_TIMEOUT_SECONDS", 900))
_CHECK_INTERVAL = int(getattr(settings, "STALE_RUN_CHECK_INTERVAL_SECONDS", 120))


async def _mark_stale_runs() -> int:
    """Marks RUNNING runs older than the stale threshold as FAILED. Returns count."""
    from app.agents.events import record_and_publish_event
    from app.db.models.run import AgentRun

    cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=_STALE_TIMEOUT)

    async with async_session_factory() as session:
        stmt = select(AgentRun).where(
            AgentRun.status == "RUNNING",
            AgentRun.updated_at < cutoff,
        )
        result = await session.execute(stmt)
        stale_runs = result.scalars().all()

        count = 0
        for run in stale_runs:
            run.status = "FAILED"
            session.add(run)
            count += 1
            log.warning(
                "agent.run.stale_detected",
                run_id=str(run.id),
                user_id=str(run.user_id),
                updated_at=run.updated_at.isoformat() if run.updated_at else None,
                stale_timeout_seconds=_STALE_TIMEOUT,
            )
            try:
                await record_and_publish_event(
                    session,
                    run.id,
                    "agent.failed",
                    "failed",
                    "Agent run timed out (stale process detection).",
                    run.plan_id,
                )
            except Exception:
                pass  # Don't let event publishing block the recovery

        if count:
            await session.commit()
            log.info("agent.run.stale_recovery", recovered=count)

        return count


async def stale_run_recovery_loop() -> None:
    """Infinite loop that periodically checks for stale runs."""
    log.info("stale_run_recovery.started", interval_seconds=_CHECK_INTERVAL)
    while True:
        try:
            count = await _mark_stale_runs()
            if count:
                log.warning("stale_run_recovery.recovered", count=count)
        except Exception:
            log.exception("stale_run_recovery.error")
        await asyncio.sleep(_CHECK_INTERVAL)
