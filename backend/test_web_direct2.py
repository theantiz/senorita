import asyncio

from google.genai import types

from app.agents.gemini_client import get_client


async def main():
    client = get_client()
    search_tool = types.Tool(google_search=types.GoogleSearch())

    # Try with gemini-2.0-flash which may have separate quota
    for model in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-3.1-flash-lite"]:
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents="What is the latest SpaceX launch in 2026?",
                config=types.GenerateContentConfig(tools=[search_tool]),
            )
            print(f"SUCCESS with {model}")
            print("Text:", (response.text or "")[:400])
            if response.candidates:
                gm = getattr(response.candidates[0], "grounding_metadata", None)
                if gm:
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    print(f"\nSources ({len(chunks)}):")
                    for chunk in chunks[:5]:
                        web = getattr(chunk, "web", None)
                        if web:
                            print(f"  - {getattr(web, 'title', '')} | {getattr(web, 'uri', '')}")
                else:
                    print("No grounding_metadata")
            break
        except Exception as e:
            print(f"FAILED {model}: {type(e).__name__}: {str(e)[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
