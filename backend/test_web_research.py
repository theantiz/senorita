import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from app.agents.orchestrator import handle_message
from app.db.models import User
from app.db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        res = await session.execute(select(User).limit(1))
        user = res.scalars().first()

        # Test 1: Time-sensitive query (should use web_research)
        print("=" * 60)
        print("TEST 1: Time-sensitive query")
        print("User: What's the latest on the India vs England cricket series?")
        print("=" * 60)
        response = await handle_message(session, user, "What's the latest on the India vs England cricket series?")
        print("\nSenorita:", response)

        print("\n" + "=" * 60)
        print("TEST 2: Static/historical query (should NOT search)")
        print("User: Who invented the telephone?")
        print("=" * 60)
        response2 = await handle_message(session, user, "Who invented the telephone?")
        print("\nSenorita:", response2)


if __name__ == "__main__":
    asyncio.run(main())
