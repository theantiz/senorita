import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import AgentEvent, AgentRun

logger = logging.getLogger(__name__)


class EventBroadcaster:
    def __init__(self):
        self.queues: dict[uuid.UUID, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue:
        q = asyncio.Queue()
        self.queues[run_id].append(q)
        return q

    def unsubscribe(self, run_id: uuid.UUID, q: asyncio.Queue):
        if run_id in self.queues and q in self.queues[run_id]:
            self.queues[run_id].remove(q)
            if not self.queues[run_id]:
                del self.queues[run_id]

    def publish(self, run_id: uuid.UUID, event: dict[str, Any]):
        for q in self.queues.get(run_id, []):
            try:
                q.put_nowait(event)
            except Exception as e:
                logger.error(f"Failed to publish event to queue for run {run_id}: {e}")


event_broadcaster = EventBroadcaster()


async def record_and_publish_event(
    session: AsyncSession,
    run_id: uuid.UUID,
    event_type: str,
    status: str,
    message: str,
    plan_id: uuid.UUID | None = None,
    step_id: str | None = None,
    metadata_payload: dict[str, Any] | None = None,
) -> AgentEvent:
    """
    Persist the event to Postgres and publish to any active WebSocket listeners.
    Ensures sequence ordering via SQL count.
    """
    from sqlalchemy import func, select

    # Calculate next sequence number
    stmt = select(func.count()).where(AgentEvent.run_id == run_id)
    count = await session.scalar(stmt)
    sequence_number = (count or 0) + 1

    event = AgentEvent(
        run_id=run_id,
        plan_id=plan_id,
        step_id=step_id,
        sequence_number=sequence_number,
        event_type=event_type,
        status=status,
        message=message,
        metadata_payload=metadata_payload or {},
    )

    session.add(event)
    await session.commit()
    await session.refresh(event)

    event_payload = {
        "event_id": str(event.id),
        "agent_run_id": str(run_id),
        "plan_id": str(plan_id) if plan_id else None,
        "step_id": step_id,
        "type": event_type,
        "status": status,
        "message": message,
        "timestamp": event.created_at.isoformat(),
        "metadata": event.metadata_payload,
        "sequence": sequence_number,
    }

    event_broadcaster.publish(run_id, event_payload)
    return event
