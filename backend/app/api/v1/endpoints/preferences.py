from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.preference import Preference
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()


class PreferenceCreate(BaseModel):
    domain: str
    preference: str
    confidence: str = "MEDIUM"
    strength: float = 0.5


class PreferenceUpdate(BaseModel):
    domain: str | None = None
    preference: str | None = None
    confidence: str | None = None
    strength: float | None = None


class PreferenceResponse(BaseModel):
    id: UUID
    domain: str
    preference: str
    confidence: str
    strength: float
    source: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[PreferenceResponse])
async def list_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(Preference).where(Preference.user_id == current_user.id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_preference(
    pref_in: PreferenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    pref = Preference(
        user_id=current_user.id,
        domain=pref_in.domain,
        preference=pref_in.preference,
        confidence=pref_in.confidence,
        strength=max(0.0, min(1.0, pref_in.strength)),
        source="explicit",
    )
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return pref


@router.patch("/{pref_id}", response_model=PreferenceResponse)
async def update_preference(
    pref_id: UUID,
    pref_in: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(Preference).where(Preference.id == pref_id, Preference.user_id == current_user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    if pref_in.domain is not None:
        pref.domain = pref_in.domain
    if pref_in.preference is not None:
        pref.preference = pref_in.preference
    if pref_in.confidence is not None:
        pref.confidence = pref_in.confidence
    if pref_in.strength is not None:
        pref.strength = max(0.0, min(1.0, pref_in.strength))

    await db.commit()
    await db.refresh(pref)
    return pref


@router.delete("/{pref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    pref_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(Preference).where(Preference.id == pref_id, Preference.user_id == current_user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    await db.delete(pref)
    await db.commit()
