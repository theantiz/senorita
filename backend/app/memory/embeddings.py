from google import genai
from google.genai import types

from app.core.config import settings

_client_instance = None


def get_client() -> genai.Client:
    global _client_instance
    if _client_instance is not None:
        return _client_instance
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    _client_instance = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client_instance


async def embed_text(text: str, task_type: str) -> list[float]:
    """
    Generate an embedding vector for the given text.
    task_type should be "RETRIEVAL_DOCUMENT" or "RETRIEVAL_QUERY".
    """
    text = text.strip()
    if not text:
        return []

    client = get_client()
    result = await client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return (result.embeddings[0].values or []) if result.embeddings else []
