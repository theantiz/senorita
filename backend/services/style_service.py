import logging
import json
import re
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Contact, EmailMessage, SlackMessage, Integration
from agents.gemini_client import get_client
from core.config import settings

logger = logging.getLogger(__name__)

def _clean_email_body(text: str) -> str:
    """Removes common email signatures and quoted replies to isolate the user's actual text."""
    # Remove standard forwarded headers
    text = re.sub(r'-----Original Message-----.*', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove common quoted reply blocks
    text = re.sub(r'On\s+.*wrote:.*', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'From:.*Sent:.*To:.*Subject:.*', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove HTML tags just in case
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

async def infer_tone_profile(session: AsyncSession, user_id: UUID, contact_id: UUID, channel: str) -> dict | None:
    """
    Infers the user's conversational style for a specific contact and channel.
    Only analyzes messages sent BY the user TO the contact.
    """
    # 1. Fetch Contact
    contact = (await session.execute(select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id))).scalars().first()
    if not contact:
        return None
        
    current_profile = contact.tone_profile.get(channel, {})
    if current_profile.get("user_override"):
        logger.info(f"Tone inference skipped for contact {contact_id} on {channel}: user_override is true.")
        return None

    # 2. Fetch the user's identity for the channel to find outbound messages
    integration = (await session.execute(select(Integration).where(Integration.user_id == user_id, Integration.provider == channel))).scalars().first()
    if not integration:
        return None
        
    outbound_messages = []
    
    if channel == "email" or channel == "gmail":
        channel_key = "email"
        # pull outbound emails directly using the direction column
        msgs = (await session.execute(
            select(EmailMessage)
            .where(EmailMessage.user_id == user_id)
            .where(EmailMessage.direction == 'outbound')
            .order_by(EmailMessage.received_at.desc())
            .limit(20)
        )).scalars().all()
        outbound_messages = [_clean_email_body(m.snippet) for m in msgs if m.snippet]
        
    elif channel == "slack":
        channel_key = "slack"
        # User's own slack ID is usually the bot's user ID or the installer's ID
        user_slack_id = integration.permissions.get("authed_user", {}).get("id") or integration.permissions.get("user_id")
        if not user_slack_id:
            logger.warning(f"Could not determine user's Slack ID from integration {integration.id}")
            return None
            
        msgs = (await session.execute(
            select(SlackMessage)
            .where(SlackMessage.user_id == user_id)
            .where(SlackMessage.from_user == user_slack_id)
            .order_by(SlackMessage.received_at.desc())
            .limit(20)
        )).scalars().all()
        outbound_messages = [m.body_snippet for m in msgs if m.body_snippet]
    else:
        return None

    if not outbound_messages:
        logger.info(f"No outbound messages found for contact {contact_id} on {channel}. Skipping inference.")
        return None
        
    # 3. Feed to Gemini
    client = get_client()
    
    samples = "\\n---\\n".join(outbound_messages[:15]) # cap at 15 for prompt size
    
    prompt = f"""
    You are an expert linguist analyzing a user's conversational tone based on their sent messages.
    Analyze the following outbound messages.
    
    Output ONLY a valid JSON object adhering to this structure (no markdown blocks, no extra text):
    {{
      "confidence": (float between 0.0 and 1.0),
      "style": {{
        "emoji": "none" | "rare" | "occasional" | "frequent",
        "sentence_length": "short" | "medium" | "long",
        "punctuation": "minimal" | "standard" | "heavy",
        "uses_exclamation": boolean,
        "uses_lowercase": boolean,
        "uses_bullet_lists": boolean,
        "uses_questions": "rare" | "occasional" | "often",
        "uses_abbreviations": [list of string abbreviations found, e.g. "pls", "btw"]
      }},
      "relationship": {{
        "warmth": "low" | "medium" | "high",
        "professionalism": "low" | "medium" | "high",
        "directness": "low" | "medium" | "high"
      }},
      "greeting_examples": [list of 1-3 greetings they actually used in the text],
      "closing_examples": [list of 1-3 closings they actually used],
      "reusable_patterns": [
        {{ "intent": "string description", "template": "string pattern they use repeatedly" }}
      ]
    }}
    
    Messages:
    {samples}
    """
    
    try:
        resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=[prompt])
        raw_json = resp.text.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:-3]
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:-3]
            
        parsed = json.loads(raw_json.strip())
        
        # 4. Merge and Save
        parsed["version"] = current_profile.get("version", 0) + 1
        parsed["updated_at"] = datetime.now(timezone.utc).isoformat()
        parsed["computed_at"] = parsed["updated_at"]
        parsed["user_override"] = False
        parsed["sample_count"] = current_profile.get("sample_count", 0) + len(outbound_messages)
        
        # We make a copy of the dictionary to ensure SQLAlchemy detects the mutation on the JSONB column
        new_profiles = dict(contact.tone_profile)
        new_profiles[channel_key] = parsed
        contact.tone_profile = new_profiles
        
        await session.commit()
        return parsed
        
    except Exception as e:
        logger.error(f"Failed to infer tone profile: {e}", exc_info=True)
        return None
