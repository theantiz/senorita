import pytest
from app.db.models.user import User
from app.db.models.autonomy_policy import AutonomyPolicy
from app.agents.tool_system.definitions import ToolDefinition, ConfirmationPolicy
from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.permissions import PermissionManager

@pytest.mark.asyncio
async def test_autonomy_policy_resolution():
    pm = PermissionManager()
    
    def1 = ToolDefinition(name="gmail.send_email", description="", input_schema={}, category="gmail", subcategory="actions", confirmation_policy=ConfirmationPolicy.ASK_ONCE)
    
    ctx = ToolContext(user_id="fake", permissions={"gmail.send_email": "SUGGEST"})
    assert pm.permission_mode(def1, ctx) == ConfirmationPolicy.NEVER_ALLOW
    
    ctx = ToolContext(user_id="fake", permissions={"gmail.send_email": "FULL_AUTO"})
    assert pm.permission_mode(def1, ctx) == ConfirmationPolicy.ALWAYS_ALLOW
    
    ctx = ToolContext(user_id="fake", permissions={"gmail.send_email": "CONFIRM"})
    assert pm.permission_mode(def1, ctx) == ConfirmationPolicy.ASK_EACH_TIME
    
    ctx = ToolContext(user_id="fake", permissions={"gmail.send_email": "TRUSTED"})
    assert pm.permission_mode(def1, ctx) == ConfirmationPolicy.ASK_ONCE
