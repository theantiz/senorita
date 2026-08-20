import asyncio
import os
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.agents.tool_registry import _handle_search_all_unanswered
from app.db.models import Contact, EmailMessage, MessageMode, SlackMessage, User
from app.db.session import async_session_factory
from app.services.message_mode_service import resolve_mode


async def run_verification():
    print("--- Starting Module 14 Verification (Live Postgres) ---")

    async with async_session_factory() as session:
        # We'll see if the user exists, else create
        user_name = "Test User"
        result = await session.execute(select(User).where(User.name == user_name))
        user = result.scalars().first()

        if not user:
            user_id = uuid4()
            user = User(id=user_id, name=user_name, timezone="UTC")
            session.add(user)
            await session.commit()
        else:
            user_id = user.id

        # Clean up past test data
        await session.execute(delete(MessageMode).where(MessageMode.user_id == user_id))
        await session.execute(delete(Contact).where(Contact.user_id == user_id))
        await session.execute(delete(EmailMessage).where(EmailMessage.user_id == user_id))
        await session.execute(delete(SlackMessage).where(SlackMessage.user_id == user_id))
        await session.commit()

        # 2. Create a Contact
        contact_id = uuid4()
        contact = Contact(id=contact_id, user_id=user_id, name="VIP Client", relationship_type="client")
        session.add(contact)

        # 3. Set Global Mode to 'approval_required'
        global_mode = MessageMode(
            user_id=user_id, scope="global", contact_id=None, channel=None, mode="approval_required"
        )
        session.add(global_mode)

        # 4. Override Contact + Slack combination to 'trusted'
        slack_override = MessageMode(
            user_id=user_id, scope="contact", contact_id=contact_id, channel="slack", mode="trusted"
        )
        session.add(slack_override)

        await session.commit()

        # --- TEST 1: Send Slack Message to VIP Client ---
        print("\n[Test 1] Resolving mode for VIP Client on Slack...")
        slack_mode = await resolve_mode(session, user_id, contact_id, "slack")
        print(f"Result: {slack_mode}")
        if slack_mode == "trusted":
            print("✅ PASS: Slack send to VIP Client is 'trusted' (goes through without confirmation).")
        else:
            print("❌ FAIL: Expected 'trusted'.")

        # --- TEST 2: Send Gmail Message to VIP Client ---
        print("\n[Test 2] Resolving mode for VIP Client on Gmail...")
        gmail_mode = await resolve_mode(session, user_id, contact_id, "gmail")
        print(f"Result: {gmail_mode}")
        if gmail_mode == "approval_required":
            print("✅ PASS: Gmail send to VIP Client fell back to global 'approval_required' (requires confirmation).")
        else:
            print("❌ FAIL: Expected 'approval_required'.")

        # --- TEST 3: search_all_unanswered() ---
        print("\n[Test 3] Testing cross-channel unanswered search...")

        from datetime import datetime, timezone

        # Add a fake unanswered email
        email = EmailMessage(
            user_id=user_id,
            gmail_message_id="gmail-123",
            thread_id="thread-123",
            from_address="vip@client.com",
            subject="Urgent question",
            snippet="Can we schedule a call?",
            received_at=datetime.now(timezone.utc),
            needs_reply=True,
        )
        session.add(email)

        # Add a fake unanswered Slack message
        slack = SlackMessage(
            user_id=user_id,
            slack_channel_id="C12345",
            slack_message_ts="1620000000.0001",
            from_user="U98765",
            body_snippet="Hey, are you free now?",
            received_at=datetime.now(timezone.utc),
            needs_reply=True,
        )
        session.add(slack)

        await session.commit()

        # Run the actual tool handler
        results = await _handle_search_all_unanswered(session, user_id)

        print("\nReal Output from _handle_search_all_unanswered():")
        import json

        print(json.dumps(results, indent=2))

        print("\nChecking against DB rows...")
        print(f"Email Row: ID={email.id}, From={email.from_address}, Snippet={email.snippet}")
        print(f"Slack Row: ID={slack.id}, From={slack.from_user}, Snippet={slack.body_snippet}")

        if len(results.get("unanswered_messages", [])) == 2:
            print("✅ PASS: Both channels successfully queried and unified.")
        else:
            print("❌ FAIL: Did not return 2 unanswered messages.")


if __name__ == "__main__":
    asyncio.run(run_verification())
