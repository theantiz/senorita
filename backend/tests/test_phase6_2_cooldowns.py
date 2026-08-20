import pytest
from datetime import datetime, timezone
from app.events.cooldown import CooldownManager
from app.db.models.user import User

@pytest.fixture
async def cooldown_user(db_session):
    u = User(name="CooldownUser", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.mark.asyncio
async def test_cooldown_manager(db_session, cooldown_user):
    # First trigger should succeed
    assert await CooldownManager.can_trigger(db_session, str(cooldown_user.id), "test_trigger", 1) == True
    # Immediate second trigger should fail
    assert await CooldownManager.can_trigger(db_session, str(cooldown_user.id), "test_trigger", 1) == False
