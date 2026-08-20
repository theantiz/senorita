import pytest
from app.api.v1.endpoints.feedback import submit_feedback, FeedbackCreate
from app.db.models.user import User
from app.db.models.run import AgentRun
from app.db.models.feedback import DecisionFeedback

@pytest.fixture
async def f_user(db_session):
    u = User(name="FUser", timezone="UTC", autonomy_level="FULL_AUTO")
    db_session.add(u)
    await db_session.commit()
    return u

@pytest.fixture
async def f_run(db_session, f_user):
    r = AgentRun(user_id=f_user.id, workflow_id="test_wf", status="COMPLETED")
    db_session.add(r)
    await db_session.commit()
    return r

@pytest.mark.asyncio
async def test_submit_feedback(db_session, f_user, f_run):
    payload = FeedbackCreate(run_id=str(f_run.id), feedback_type="HELPFUL")
    res = await submit_feedback(payload, db_session, f_user)
    assert res["status"] == "ok"

