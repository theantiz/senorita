from google import genai
from core.config import settings

def get_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def call_model(input_content: str, tools: list | None = None, previous_interaction_id: str | None = None):
    client = get_client()
    # If there are tools, interactions.create will handle them if we provide them as tool declarations.
    # The new google-genai SDK 2.3.0 introduced interactions API.
    interaction = client.interactions.create(
        model="gemini-3.5-flash",
        input=input_content,
        tools=tools,
        previous_interaction_id=previous_interaction_id
    )
    return interaction
