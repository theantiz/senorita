import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import Contact, MessageMode, User
from app.schemas.message_mode import MessageModeCreate, MessageModeRead, MessageModeUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/message-modes", tags=["message-modes"])


@router.get("", response_model=list[MessageModeRead])
async def list_message_modes(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: str | None = Query(None, description="Filter by scope ('global' or 'contact')"),
):
    """
    List message mode overrides.
    """
    stmt = select(MessageMode).where(MessageMode.user_id == current_user.id)
    if scope:
        stmt = stmt.where(MessageMode.scope == scope)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.patch("/{mode_id}", response_model=MessageModeRead)
async def update_message_mode(
    mode_id: UUID,
    mode_update: MessageModeUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing message mode override.
    """
    stmt = select(MessageMode).where(MessageMode.id == mode_id, MessageMode.user_id == current_user.id)
    result = await session.execute(stmt)
    mode = result.scalars().first()

    if not mode:
        raise HTTPException(status_code=404, detail="Message mode not found")

    if mode_update.mode is not None:
        mode.mode = mode_update.mode

    await session.commit()
    await session.refresh(mode)
    return mode


@router.post("", response_model=MessageModeRead)
async def create_message_mode(
    mode_create: MessageModeCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new message mode override.
    """
    # Check if this precise combination already exists
    stmt = select(MessageMode).where(
        MessageMode.user_id == current_user.id,
        MessageMode.scope == mode_create.scope,
        MessageMode.contact_id == mode_create.contact_id,
        MessageMode.channel == mode_create.channel,
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        existing.mode = mode_create.mode
        await session.commit()
        await session.refresh(existing)
        return existing

    new_mode = MessageMode(
        user_id=current_user.id,
        scope=mode_create.scope,
        contact_id=mode_create.contact_id,
        channel=mode_create.channel,
        mode=mode_create.mode,
    )
    session.add(new_mode)
    await session.commit()
    await session.refresh(new_mode)
    return new_mode


@router.delete("/{mode_id}")
async def delete_message_mode(
    mode_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete a message mode override.
    """
    stmt = select(MessageMode).where(MessageMode.id == mode_id, MessageMode.user_id == current_user.id)
    result = await session.execute(stmt)
    mode = result.scalars().first()

    if not mode:
        raise HTTPException(status_code=404, detail="Message mode not found")

    await session.delete(mode)
    await session.commit()
    return {"status": "ok"}
