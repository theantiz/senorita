from google import genai
from core.config import settings

def get_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.GEMINI_API_KEY)

async def embed_text(text: str, task_type: str) -> list[float]:
    """
    Generate an embedding vector for the given text.
    task_type should be "RETRIEVAL_DOCUMENT" or "RETRIEVAL_QUERY".
    """
    client = get_client()
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=genai.types.EmbedContentConfig(task_type=task_type)
    )
    return result.embeddings[0].values if result.embeddings else []
