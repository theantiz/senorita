from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.memory_entry import MemoryEntryCreate, MemoryEntryRead, MemoryEntryUpdate
from app.services.memory_service import (
    create_memory,
    delete_all_memories,
    delete_memory,
    get_memories,
    get_memory,
    update_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])

from datetime import datetime


@router.get("", response_model=list[MemoryEntryRead])
async def list_memories(
    search: str | None = Query(None),
    memory_type: str | None = Query(None),
    source_ref: str | None = Query(None),
    locked: bool | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_memories(
        session,
        current_user.id,
        search=search,
        memory_type=memory_type,
        source_ref=source_ref,
        locked=locked,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=MemoryEntryRead)
async def create_new_memory(
    memory_in: MemoryEntryCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_memory(session, current_user.id, memory_in)


@router.delete("")
async def delete_all_existing_memories(
    session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    count = await delete_all_memories(session, current_user.id)
    return {"ok": True, "deleted": count}


@router.delete("/{memory_id}")
async def delete_existing_memory(
    memory_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    success = await delete_memory(session, current_user.id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


@router.patch("/{memory_id}", response_model=MemoryEntryRead)
async def patch_existing_memory(
    memory_id: UUID,
    memory_update: MemoryEntryUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memory = await update_memory(session, current_user.id, memory_id, memory_update)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory
