from fastapi import APIRouter

from app.core.state import get_pause_state, set_pause_state

router = APIRouter(prefix="/system", tags=["System"])

@router.get("/status")
async def get_system_status():
    return {"status": "ok", "paused": get_pause_state()}

@router.patch("/pause")
async def pause_system():
    set_pause_state(True)
    return {"status": "paused", "message": "System background tasks paused."}

@router.patch("/resume")
async def resume_system():
    set_pause_state(False)
    return {"status": "resumed", "message": "System background tasks resumed."}
