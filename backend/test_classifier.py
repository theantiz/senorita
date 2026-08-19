import asyncio
import os
import json
from datetime import datetime
from uuid import UUID

from app.core.config import settings
from app.agents.gemini_client import start_chat

async def main():
    chat = start_chat()
    prompt = f"""Analyze the following exchange. Did the user mention a durable fact about their life worth remembering that wasn't already explicitly stored? 
If yes, extract it as a single sentence. Return ONLY a JSON object with:
'has_fact': boolean,
'fact': string (the sentence),
'category': string (one of: person, preference, date, promise, context),
'confidence': float (0.0 to 1.0)
If category is 'promise', also extract:
'subject': string (what the user promised to do),
'contact_name': string or null (who they promised it to or about),
'due_at': string or null (resolve any relative due date like 'tomorrow' into an ISO 8601 timestamp using the current date: 2026-08-15T16:00:00Z. If a date/time is not clearly specified, leave as null)

User: I should reach out to her sometime
Assistant: That sounds like a good idea.
"""
    response = await chat.send_message(prompt)
    text = (response.text or '').strip()
    if text.startswith("```json"):
        text = text[7:-3]
    elif text.startswith("```"):
        text = text[3:-3]
    data = json.loads(text)
    print("CLASSIFIER OUTPUT:")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
