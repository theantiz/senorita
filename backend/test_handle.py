import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import async_session_factory
from db.models import User
from sqlalchemy import select
from agents.orchestrator import handle_message

async def main():
    async with async_session_factory() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            print("No user found")
            return
        
        try:
            print(f"Testing for user {user.name}")
            resp = await handle_message(session, user, "Create a reminder to buy milk.")
            print(f"Response: {resp}")
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(main())
