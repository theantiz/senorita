from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db.models import Reminder, User
from app.workers.reminders.scheduler import check_reminders

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from zoneinfo import ZoneInfo


@pytest.mark.asyncio
async def test_check_reminders_fires_past_reminder(db_session):
    # Setup test user
    user = User(name="worker_test_user", timezone="UTC")
    db_session.add(user)
    await db_session.flush()

    # Create a reminder scheduled 1 hour ago
    past_time = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)

    reminder = Reminder(
        user_id=user.id,
        type="time",
        status="active",
        trigger_payload={"datetime": past_time.isoformat(), "note": "Test reminder"},
    )
    db_session.add(reminder)
    await db_session.commit()

    # Run the worker function directly
    # We mock dispatch_notification so it doesn't try to send a real system notification
    # We also mock async_session_factory so the worker queries the test DB, not the dev DB
    from tests.conftest import test_async_session_factory

    with (
        patch("app.workers.reminders.scheduler.dispatch_notification") as mock_dispatch,
        patch("app.workers.reminders.scheduler.async_session_factory", new=test_async_session_factory),
    ):
        await check_reminders()

        # Verify it dispatched
        mock_dispatch.assert_called_once()
        args, kwargs = mock_dispatch.call_args
        assert kwargs["title"] == "Reminder"
        assert kwargs["message"] == "Test reminder"

    # Verify DB state was updated
    await db_session.refresh(reminder)
    assert reminder.status == "fired"
