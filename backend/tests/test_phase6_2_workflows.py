import pytest
from app.agents.workflows.engine import execute_workflow
from app.db.models.user import User
from app.db.models.run import AgentRun
from sqlalchemy import select

@pytest.fixture
async def wf_user(db_session):
    u = User(name="WfUser", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.mark.asyncio
async def test_workflow_execution(db_session, wf_user, mocker):
    mocker.patch('app.workers.briefings.daily_briefing.generate_daily_briefing')
    await execute_workflow(db_session, wf_user, "daily_planning", {"id": "trigger_1"})
    
    stmt = select(AgentRun).where(AgentRun.user_id == wf_user.id)
    res = await db_session.execute(stmt)
    runs = res.scalars().all()
    assert len(runs) == 1
    assert runs[0].autonomous == True
    assert runs[0].workflow_id == "daily_planning"
    assert runs[0].trigger_event_id == "trigger_1"
