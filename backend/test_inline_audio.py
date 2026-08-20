import asyncio
import io
import os

from google import genai
from google.genai import types


async def main():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    # create a dummy wav or read an existing one
    # I see garbled.wav and mom.wav in the root directory!
    with open("../mom.wav", "rb") as f:
        audio_bytes = f.read()

    part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")

    response = await client.aio.models.generate_content(
        model="gemini-3.1-flash-lite", contents=[part, "Transcribe this audio."]
    )
    print("Transcription:", response.text)


if __name__ == "__main__":
    asyncio.run(main())
