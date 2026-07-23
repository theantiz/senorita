from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from db.models import MemoryEntry
from schemas.memory_entry import MemoryEntryCreate, MemoryEntryUpdate

async def get_memories(session: AsyncSession, user_id: UUID, category: str | None = None) -> list[MemoryEntry]:
    stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
    if category:
        stmt = stmt.where(MemoryEntry.category == category)
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
