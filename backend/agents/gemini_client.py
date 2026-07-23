from google import genai
from google.genai import types
from core.config import settings

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
    )
    return client.aio.chats.create(model="gemini-3.1-flash-lite", config=config)
