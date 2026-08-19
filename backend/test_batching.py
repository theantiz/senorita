import asyncio
import os
import uuid
from uuid import UUID
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from zoneinfo import ZoneInfo
from sqlalchemy import select

from app.db.session import async_session_factory
from app.db.models import User, EmailMessage, ActionLog
from app.agents.orchestrator import handle_message

async def main():
    async with async_session_factory() as session:
        # Get a user
        res = await session.execute(select(User).limit(1))
        user = res.scalars().first()
        
        # Clear existing emails to ensure exact test state
        await session.execute(EmailMessage.__table__.delete().where(EmailMessage.user_id == user.id))
        
        now = datetime.now(ZoneInfo("UTC"))
        # Insert 3 pending emails
        e1 = EmailMessage(user_id=user.id, gmail_message_id=str(uuid.uuid4()), thread_id="t1", from_address="alice@example.com", snippet="Hi, can you send the report?", needs_reply=True, received_at=now, subject="Report")
        e2 = EmailMessage(user_id=user.id, gmail_message_id=str(uuid.uuid4()), thread_id="t2", from_address="bob@example.com", snippet="Are we still on for tomorrow?", needs_reply=True, received_at=now, subject="Meeting")
        e3 = EmailMessage(user_id=user.id, gmail_message_id=str(uuid.uuid4()), thread_id="t3", from_address="charlie@example.com", snippet="Please review the attached.", needs_reply=True, received_at=now, subject="Review")
        
        session.add_all([e1, e2, e3])
        await session.commit()
        
        print(f"Inserted 3 pending emails for user {user.id}")
        
        print("\nUser says: I have some free time. What should I knock out?")
        response = await handle_message(session, user, "I have some free time. What should I knock out? Do I have any batches pending?")
        print("\nSenorita's initial response:")
        print(response)
        
        print("\nUser says: Yes, let's batch draft all 3 of them right now.")
        response2 = await handle_message(session, user, "Yes, let's batch draft all 3 of them right now.")
        print("\nSenorita's drafting response:")
        print(response2)
        
        # Print action logs
        res = await session.execute(select(ActionLog).where(ActionLog.user_id == user.id, ActionLog.action_type == 'draft_email_reply').order_by(ActionLog.created_at.desc()).limit(5))
        logs = res.scalars().all()
        print("\nRecent Draft Actions:")
        for log in logs:
            print(f"{log.action_type} for payload: {log.payload.get('email_id')} -> {log.result}")

if __name__ == "__main__":
    asyncio.run(main())
