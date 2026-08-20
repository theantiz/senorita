import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MessageMode

logger = logging.getLogger(__name__)


async def resolve_mode(session: AsyncSession, user_id: UUID, contact_id: Optional[UUID], channel: Optional[str]) -> str:
    """
    Resolve the correct message mode based on precedence:
    1. contact + channel row
    2. contact row (channel null)
    3. global row (contact null, channel null)
    4. system default ('approval_required')
    """
    # We will fetch all modes for this user to avoid multiple queries,
    # then filter in memory since the number of modes per user is small.
    stmt = select(MessageMode).where(MessageMode.user_id == user_id)
    result = await session.execute(stmt)
    modes = result.scalars().all()

    # 1. Contact + Channel
    if contact_id and channel:
        for m in modes:
            if m.scope == "contact" and m.contact_id == contact_id and m.channel == channel:
                return m.mode

    # 2. Contact (all channels)
    if contact_id:
        for m in modes:
            if m.scope == "contact" and m.contact_id == contact_id and m.channel is None:
                return m.mode

    # 3. Global (all contacts, all channels)
    for m in modes:
        if m.scope == "global" and m.contact_id is None and m.channel is None:
            return m.mode

    # 4. System default
    return "approval_required"
