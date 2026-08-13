from google import genai
from google.genai import types

from app.core.config import settings

_client_instance = None

def get_client() -> genai.Client:
    global _client_instance
    if _client_instance is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")
        _client_instance = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client_instance

def start_chat(tools: list | None = None, system_instruction: str = None):
    client = get_client()
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=system_instruction,
        # Disable thinking to avoid thought_signature requirement when using
        # function calls in multi-turn chats. Thinking models require the
        # thought_signature to be preserved across turns, which breaks when
        # history is reconstructed from the DB.
        thinking_config=types.ThinkingConfig(include_thoughts=False),
    )
    return client.aio.chats.create(model=settings.GEMINI_MODEL, config=config)
