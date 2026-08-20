import pytest
from app.api.v1.endpoints.productivity import FocusStart, start_focus, stop_focus, get_focus_status
from app.db.models.user import User

@pytest.fixture
async def p_user(db_session):
    u = User(name="PUser", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.mark.asyncio
async def test_focus_mode_lifecycle(db_session, p_user):
    payload = FocusStart(duration_minutes=60, task_id="task1")
    res1 = await start_focus(payload, db_session, p_user)
    assert res1["status"] == "ACTIVE"
    
    res2 = await get_focus_status(db_session, p_user)
    assert res2["active"] == True
    assert res2["duration"] == 60
    
    res3 = await stop_focus(db_session, p_user)
    assert res3["status"] == "COMPLETED"
    
    res4 = await get_focus_status(db_session, p_user)
    assert res4["active"] == False
