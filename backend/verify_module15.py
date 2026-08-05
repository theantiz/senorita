import asyncio
import os
import json
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete
from db.models import User, Contact, SlackMessage, Integration
from services.style_service import infer_tone_profile
from agents.tool_registry import _handle_draft_slack_reply
from db.session import async_session_factory

async def run_verification():
    print("--- Starting Module 15 Verification ---")
    
    async with async_session_factory() as session:
        # Create or fetch user
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
            
        # Clear out past data for clean test
        await session.execute(delete(Contact).where(Contact.user_id == user_id))
        await session.execute(delete(SlackMessage).where(SlackMessage.user_id == user_id))
        await session.execute(delete(Integration).where(Integration.user_id == user_id))
        await session.commit()
        
        # Add mock integration so we know the user's slack ID
        user_slack_id = "U12345"
        integration = Integration(
            user_id=user_id,
            provider="slack",
            status="connected",
            permissions={"user_id": user_slack_id}
        )
        session.add(integration)
        
        # Create a Contact
        contact_id = uuid4()
        contact = Contact(id=contact_id, user_id=user_id, name="Buddy", relationship_type="friend")
        session.add(contact)
        
        # Create an INBOUND message that we will reply to later
        inbound = SlackMessage(
            user_id=user_id,
            slack_channel_id="C_BUDDY",
            slack_message_ts="1000000000.0001",
            from_user="U_BUDDY",
            channel_name="Buddy",
            body_snippet="Hey man, are we still on for lunch tomorrow?",
            received_at=datetime.now(timezone.utc),
            needs_reply=True
        )
        session.add(inbound)
        await session.flush()
        inbound_id = inbound.id
        
        # Seed 10 OUTBOUND casual messages to "Buddy"
        casual_messages = [
            "yo! yeah totally.",
            "nah I can't make it today. sry bro 😭",
            "haha yeah that was wild!!",
            "omg 😂",
            "btw can you send me that link?",
            "pls don't forget the tickets",
            "cool see ya later",
            "dude what time?",
            "bet.",
            "hey man, running 5 mins late!"
        ]
        
        for i, text in enumerate(casual_messages):
            msg = SlackMessage(
                user_id=user_id,
                slack_channel_id="C_BUDDY",
                slack_message_ts=f"1000000000.000{i+2}",
                from_user=user_slack_id, # User sent this
                channel_name="Buddy",
                body_snippet=text,
                received_at=datetime.now(timezone.utc),
                needs_reply=False # outbound
            )
            session.add(msg)
            
        await session.commit()
        
        print("\n[Test 1] Running infer_tone_profile...")
        profile = await infer_tone_profile(session, user_id, contact_id, "slack")
        print("Inferred Profile JSON:")
        print(json.dumps(profile, indent=2))
        
        print("\n[Test 2] Generating auto-inferred draft...")
        # Reload contact to get updated profile in memory
        await session.refresh(contact)
        
        draft = await _handle_draft_slack_reply(session, user_id, str(inbound.slack_channel_id), "Confirm lunch is still on for tomorrow.")
        print("Draft Output:")
        print(draft)
        
        print("\n[Test 3] Setting user_override to formal...")
        formal_profile = {
            "user_override": True,
            "style": {
                "formality": "formal",
                "emoji": "none",
                "sentence_length": "medium",
                "punctuation": "standard",
                "uses_lowercase": False,
                "uses_exclamation": False
            },
            "greeting_examples": ["Dear Buddy", "Hello Buddy"],
            "closing_examples": ["Best regards", "Sincerely"]
        }
        
        new_profiles = dict(contact.tone_profile)
        new_profiles["slack"] = formal_profile
        contact.tone_profile = new_profiles
        await session.commit()
        
        print("\n[Test 4] Generating formal override draft...")
        draft2 = await _handle_draft_slack_reply(session, user_id, str(inbound.slack_channel_id), "Confirm lunch is still on for tomorrow.")
        print("Draft Output:")
        print(draft2)

if __name__ == "__main__":
    asyncio.run(run_verification())
