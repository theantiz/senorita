import asyncio

import httpx
from sqlalchemy import select

from app.db.models import AuthToken, User
from app.db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        auth_tokens = (await session.execute(select(AuthToken))).scalars().all()
        if not auth_tokens:
            print("No tokens found in DB.")
            return

        # Try to find a user and login to get a real token, or just use the first one if we can reverse it?
        # We can't reverse the hash. We have to login to get a raw token.

        # Let's create a new user/token
        async with httpx.AsyncClient() as client:
            res = await client.post("http://localhost:8000/auth/setup", json={"name": "Test", "timezone": "UTC"})
            if res.status_code != 200:
                print("Failed to setup auth:", res.text)
                return
            token = res.json()["token"]

            # Test chat
            res_chat = await client.post(
                "http://localhost:8000/chat", headers={"Authorization": f"Bearer {token}"}, json={"message": "hello"}
            )
            print("Chat response:", res_chat.status_code)

            # Test voice
            files = {"audio": ("test.webm", b"fake audio data", "audio/webm")}
            res_voice = await client.post(
                "http://localhost:8000/chat/voice", headers={"Authorization": f"Bearer {token}"}, files=files
            )
            print("Voice response:", res_voice.status_code, res_voice.text)


if __name__ == "__main__":
    asyncio.run(main())
