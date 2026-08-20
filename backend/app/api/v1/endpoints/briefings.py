import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import Briefing, User

router = APIRouter(tags=["Briefings"])


class BriefingSettingsUpdate(BaseModel):
    briefing_time: str | None = None
    briefing_enabled: bool | None = None
    briefing_detail_level: str | None = None


@router.get("/briefings/latest")
async def get_latest_briefing(
    type: str = Query(..., description="Type of briefing (e.g. daily)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Briefing)
        .where(Briefing.user_id == current_user.id, Briefing.type == type)
        .order_by(desc(Briefing.created_at))
        .limit(1)
    )

    result = await db.execute(stmt)
    briefing = result.scalar_one_or_none()

    if not briefing:
        return {"status": "success", "data": None}

    return {
        "status": "success",
        "data": {
            "id": str(briefing.id),
            "type": briefing.type,
            "content": briefing.content,
            "created_at": briefing.created_at.isoformat(),
        },
    }


@router.patch("/settings/briefing")
async def update_briefing_settings(
    settings: BriefingSettingsUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if settings.briefing_time is not None:
        current_user.briefing_time = settings.briefing_time
    if settings.briefing_enabled is not None:
        current_user.briefing_enabled = settings.briefing_enabled
    if settings.briefing_detail_level is not None:
        if settings.briefing_detail_level not in ["brief", "standard", "detailed"]:
            raise HTTPException(status_code=400, detail="Invalid detail level")
        current_user.briefing_detail_level = settings.briefing_detail_level

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return {
        "status": "success",
        "data": {
            "briefing_time": current_user.briefing_time,
            "briefing_enabled": current_user.briefing_enabled,
            "briefing_detail_level": current_user.briefing_detail_level,
        },
    }


class EodBriefingSettingsUpdate(BaseModel):
    eod_briefing_time: str | None = None
    eod_briefing_enabled: bool | None = None
    eod_briefing_detail_level: str | None = None


@router.patch("/settings/eod-briefing")
async def update_eod_briefing_settings(
    settings: EodBriefingSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if settings.eod_briefing_time is not None:
        current_user.eod_briefing_time = settings.eod_briefing_time
    if settings.eod_briefing_enabled is not None:
        current_user.eod_briefing_enabled = settings.eod_briefing_enabled
    if settings.eod_briefing_detail_level is not None:
        if settings.eod_briefing_detail_level not in ["brief", "standard", "detailed"]:
            raise HTTPException(status_code=400, detail="Invalid detail level")
        current_user.eod_briefing_detail_level = settings.eod_briefing_detail_level

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return {
        "status": "success",
        "data": {
            "eod_briefing_time": current_user.eod_briefing_time,
            "eod_briefing_enabled": current_user.eod_briefing_enabled,
            "eod_briefing_detail_level": current_user.eod_briefing_detail_level,
        },
    }
