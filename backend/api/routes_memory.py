from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from db.session import get_db
from db.models import User
from schemas.memory_entry import MemoryEntryCreate, MemoryEntryRead
from services.memory_service import get_memories, get_memory, create_memory, delete_memory
from core.security import get_current_user

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("", response_model=list[MemoryEntryRead])
async def list_memories(category: str | None = Query(None), session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_memories(session, current_user.id, category=category)

@router.post("", response_model=MemoryEntryRead)
async def create_new_memory(memory_in: MemoryEntryCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_memory(session, current_user.id, memory_in)

@router.delete("/{memory_id}")
async def delete_existing_memory(memory_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_memory(session, current_user.id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}

@router.patch("/{memory_id}/lock", response_model=MemoryEntryRead)
async def toggle_memory_lock(memory_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    memory = await get_memory(session, current_user.id, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    memory.locked = not memory.locked
    await session.commit()
    await session.refresh(memory)
    return memory
