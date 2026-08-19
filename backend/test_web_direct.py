import asyncio
import json
from app.agents.gemini_client import get_client
from google.genai import types
from app.core.config import settings

async def main():
    client = get_client()
    search_tool = types.Tool(google_search=types.GoogleSearch())
    prompt = "What is the latest on the India vs England cricket series in August 2026?"
    
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[search_tool],
            ),
        )
        print("SUCCESS")
        print("Text:", response.text[:500] if response.text else "None")
        if response.candidates:
            c = response.candidates[0]
            gm = getattr(c, "grounding_metadata", None)
            if gm:
                chunks = getattr(gm, "grounding_chunks", None) or []
                print(f"\nGrounding chunks: {len(chunks)}")
                for chunk in chunks[:5]:
                    web = getattr(chunk, "web", None)
                    if web:
                        print(f"  - {getattr(web, 'title', '')} | {getattr(web, 'uri', '')}")
            else:
                print("No grounding_metadata")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
