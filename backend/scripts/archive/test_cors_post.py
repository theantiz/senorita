import asyncio

import httpx


async def main():
    async with httpx.AsyncClient() as client:
        with open("test.wav", "wb") as f:
            f.write(b"fake audio data")

        with open("test.wav", "rb") as f:
            files = {"audio": ("voice.webm", f, "audio/webm")}
            headers = {
                "Origin": "http://localhost:3000",
                "Authorization": "Bearer mock-token"
            }
            try:
                response = await client.post("http://localhost:8000/chat/voice", files=files, headers=headers)
                print("Status:", response.status_code)
                print("Headers:", response.headers)
                print("Body:", response.text)
            except Exception as e:
                print("Exception:", e)

asyncio.run(main())
