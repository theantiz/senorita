"""
Per-user LLM usage accounting and cost control.

Tracks daily token consumption and cost per user, enforces configurable
limits, and persists daily usage to Postgres so limits survive restarts.

Usage:
    from app.core.usage import UsageAccounting, UsageExceededError
    accounting = UsageAccounting(session, user_id)
    await accounting.check_and_record(input_tokens=500, output_tokens=200)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import llm_input_tokens_total, llm_output_tokens_total

log = get_logger(__name__)

# Cost constants — USD per 1M tokens (adjust per model pricing)
_COST_PER_1M_INPUT = 0.075   # Gemini Flash lite input
_COST_PER_1M_OUTPUT = 0.30   # Gemini Flash lite output


class UsageExceededError(Exception):
    """Raised when a per-user daily limit has been reached."""
    def __init__(self, limit_type: str, limit: float, current: float):
        self.limit_type = limit_type
        self.limit = limit
        self.current = current
        super().__init__(
            f"Daily {limit_type} limit reached ({current:.0f}/{limit:.0f}). "
            "Your daily AI usage limit has been reached."
        )


@dataclass
class UsageSummary:
    date: date
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    agent_runs: int
    tool_invocations: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * _COST_PER_1M_INPUT + output_tokens * _COST_PER_1M_OUTPUT) / 1_000_000


class UsageAccounting:
    """
    Records per-user daily LLM usage and enforces configured limits.

    Limits (from Settings / environment):
        DAILY_TOKEN_LIMIT    - total tokens per day (0 = unlimited)
        DAILY_COST_LIMIT_USD - estimated USD cost per day (0 = unlimited)
        DAILY_AGENT_RUN_LIMIT - agent runs per day (0 = unlimited)
    """

    def __init__(self, session: AsyncSession, user_id: uuid.UUID, provider: str = "gemini", model: str = "") -> None:
        self.session = session
        self.user_id = user_id
        self.provider = provider
        self.model = model or settings.GEMINI_MODEL

    async def check_and_record(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        run_id: str | None = None,
        dry_run: bool = False,
    ) -> UsageSummary:
        """
        Check limits then record usage.

        Raises UsageExceededError if any configured limit would be exceeded.
        Pass dry_run=True to only check without recording.
        """
        today = date.today()
        existing = await self._load_or_create(today)

        # Check limits
        daily_token_limit = getattr(settings, "DAILY_TOKEN_LIMIT", 0)
        daily_cost_limit = getattr(settings, "DAILY_COST_LIMIT_USD", 0.0)

        projected_tokens = existing.input_tokens + existing.output_tokens + input_tokens + output_tokens
        projected_cost = _estimate_cost(
            existing.input_tokens + input_tokens,
            existing.output_tokens + output_tokens,
        )

        if daily_token_limit and projected_tokens > daily_token_limit:
            raise UsageExceededError("token", daily_token_limit, projected_tokens)
        if daily_cost_limit and projected_cost > daily_cost_limit:
            raise UsageExceededError("cost_usd", daily_cost_limit, projected_cost)

        if not dry_run:
            await self._increment(today, input_tokens, output_tokens)

            # Update Prometheus counters
            llm_input_tokens_total.labels(provider=self.provider, model=self.model).inc(input_tokens)
            llm_output_tokens_total.labels(provider=self.provider, model=self.model).inc(output_tokens)

            log.info(
                "llm.usage.recorded",
                user_id=str(self.user_id),
                run_id=run_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=round(_estimate_cost(input_tokens, output_tokens), 6),
            )

        return UsageSummary(
            date=today,
            input_tokens=existing.input_tokens + (0 if dry_run else input_tokens),
            output_tokens=existing.output_tokens + (0 if dry_run else output_tokens),
            estimated_cost_usd=projected_cost,
            agent_runs=existing.agent_runs,
            tool_invocations=existing.tool_invocations,
        )

    async def increment_agent_run(self) -> None:
        today = date.today()
        existing = await self._load_or_create(today)

        daily_run_limit = getattr(settings, "DAILY_AGENT_RUN_LIMIT", 0)
        if daily_run_limit and existing.agent_runs >= daily_run_limit:
            raise UsageExceededError("agent_run", daily_run_limit, existing.agent_runs)

        await self.session.execute(
            update(_DailyUsage).where(
                _DailyUsage.user_id == self.user_id,
                _DailyUsage.usage_date == today,
            ).values(agent_runs=_DailyUsage.agent_runs + 1)
        )
        await self.session.commit()

    async def _load_or_create(self, today: date) -> "_DailyUsage":
        stmt = select(_DailyUsage).where(
            _DailyUsage.user_id == self.user_id,
            _DailyUsage.usage_date == today,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = _DailyUsage(user_id=self.user_id, usage_date=today)
            self.session.add(row)
            await self.session.flush()
        return row

    async def _increment(self, today: date, input_t: int, output_t: int) -> None:
        cost = _estimate_cost(input_t, output_t)
        await self.session.execute(
            update(_DailyUsage).where(
                _DailyUsage.user_id == self.user_id,
                _DailyUsage.usage_date == today,
            ).values(
                input_tokens=_DailyUsage.input_tokens + input_t,
                output_tokens=_DailyUsage.output_tokens + output_t,
                estimated_cost_usd=_DailyUsage.estimated_cost_usd + cost,
            )
        )
        await self.session.commit()


# ─── SQLAlchemy Model ─────────────────────────────────────────────────────────

from sqlalchemy import Column, Date, Float, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.base import Base  # noqa: E402


class _DailyUsage(Base):
    __tablename__ = "daily_usage"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    usage_date = Column(Date, nullable=False)
    input_tokens = Column(Integer, nullable=False, server_default="0")
    output_tokens = Column(Integer, nullable=False, server_default="0")
    estimated_cost_usd = Column(Float, nullable=False, server_default="0")
    agent_runs = Column(Integer, nullable=False, server_default="0")
    tool_invocations = Column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"),
    )
