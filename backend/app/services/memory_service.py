from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry
from app.memory.embeddings import embed_text
from app.schemas.memory_entry import MemoryEntryCreate, MemoryEntryUpdate


async def get_memories(
    session: AsyncSession,
    user_id: UUID,
    search: str | None = None,
    memory_type: str | None = None,
    source_ref: str | None = None,
    locked: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None
) -> list[MemoryEntry]:
    stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)

    if memory_type:
        stmt = stmt.where(MemoryEntry.memory_type == memory_type)
    if source_ref:
        stmt = stmt.where(MemoryEntry.source_ref == source_ref)
    if locked is not None:
        stmt = stmt.where(MemoryEntry.locked == locked)
    if date_from:
        stmt = stmt.where(MemoryEntry.created_at >= date_from)
    if date_to:
        stmt = stmt.where(MemoryEntry.created_at <= date_to)

    if search:
        query_embedding = await embed_text(search, "RETRIEVAL_QUERY")
        if query_embedding:
            stmt = stmt.order_by(MemoryEntry.embedding.cosine_distance(query_embedding))
            # Arbitrary threshold to ensure somewhat relevant results (distance < 0.3 means similarity > 0.7)
            # We'll just order by distance for now to avoid excluding items unexpectedly,
            # or maybe limit distance < 0.4. Let's just order by distance and let the UI show top matches.
    else:
        stmt = stmt.order_by(MemoryEntry.created_at.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> MemoryEntry | None:
    stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id, MemoryEntry.id == memory_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_memory(session: AsyncSession, user_id: UUID, memory_in: MemoryEntryCreate) -> MemoryEntry:
    memory = MemoryEntry(user_id=user_id, **memory_in.model_dump())
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory

async def update_memory(session: AsyncSession, user_id: UUID, memory_id: UUID, memory_in: MemoryEntryUpdate) -> MemoryEntry | None:
    memory = await get_memory(session, user_id, memory_id)
    if not memory:
        return None
    for k, v in memory_in.model_dump(exclude_unset=True).items():
        setattr(memory, k, v)
    await session.commit()
    await session.refresh(memory)
    return memory

async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    memory = await get_memory(session, user_id, memory_id)
    if not memory:
        return False
    await session.delete(memory)
    await session.commit()
    return True
