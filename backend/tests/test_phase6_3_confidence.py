import pytest
from app.agents.tool_system.permissions import PermissionManager
from app.agents.tool_system.definitions import ToolDefinition
from app.agents.tool_system import ConfirmationPolicy, ToolContext
from app.db.models.user import User

@pytest.fixture
async def c_user(db_session):
    u = User(name="CUser", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.mark.asyncio
async def test_confidence_downgrades(db_session, c_user):
    tool = ToolDefinition(name="gmail.send_email", description="", input_schema={}, category="gmail", subcategory="actions", confirmation_policy=ConfirmationPolicy.ALWAYS_ALLOW)
    
    # Missing permissions completely => Fallback logic applies
    ctx_low = ToolContext(user_id=c_user.id, permissions={}, metadata={"confidence": 0.50})
    pm = PermissionManager()
    res_low = pm.permission_mode(tool, ctx_low)
    # The default for FULL_AUTO used to be ALWAYS_ALLOW. But with 0.50 confidence, it is NEVER_ALLOW
    assert res_low == ConfirmationPolicy.NEVER_ALLOW
    
