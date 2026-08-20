from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry


async def search_similar_memory(
    session: AsyncSession, user_id: UUID, query_embedding: list[float], top_k: int = 5
) -> list[MemoryEntry]:
    """
    Perform a cosine-distance query against memory_entries.embedding.
    Scopes to user_id, excludes locked rows, ordered by distance.
    """
    stmt = (
        select(MemoryEntry)
        .where(MemoryEntry.user_id == user_id)
        .where(MemoryEntry.locked == False)
        .order_by(MemoryEntry.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
