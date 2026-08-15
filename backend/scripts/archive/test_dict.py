import asyncio

from google.genai import types

from app.agents.gemini_client import get_client

SENORITA_TOOLS_MANUAL = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="default_api:create_reminder",
                description="Set a reminder for the user. Type is one of: time, date, recurring, event, context, location.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "type": types.Schema(type=types.Type.STRING),
                        "trigger_payload": types.Schema(type=types.Type.OBJECT)
                    }
                )
            )
        ]
    )
]

def find_thought_signature(obj):
    if isinstance(obj, dict):
        if "thought_signature" in obj or "thoughtSignature" in obj:
            print("FOUND IN DICT:", obj.get("thought_signature", obj.get("thoughtSignature")))
        for v in obj.values():
            find_thought_signature(v)
    elif isinstance(obj, list):
        for v in obj:
            find_thought_signature(v)
    elif hasattr(obj, "__dict__"):
        find_thought_signature(obj.__dict__)
        if hasattr(obj, "model_extra") and obj.model_extra:
            find_thought_signature(obj.model_extra)

async def main():
    client = get_client()
    contents = [
        {"role": "user", "parts": [{"text": "Create a reminder to buy milk."}]}
    ]
    config = types.GenerateContentConfig(tools=SENORITA_TOOLS_MANUAL, temperature=0.0)  # type: ignore[reportArgumentType]

    print("Calling Turn 1...")
    resp1 = await client.aio.models.generate_content(
        model="gemini-3.1-flash-lite", contents=contents, config=config  # type: ignore[reportArgumentType]
    )
    print("Turn 1 complete!")

    # Try to find thought_signature anywhere in the response!
    find_thought_signature(resp1)

    # Also dump the raw dict if it exists
    print("Response extra:", getattr(resp1, "model_extra", None))

asyncio.run(main())
