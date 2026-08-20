import asyncio

from sqlalchemy import select, text

from app.db.models import ActionLog, Conversation
from app.db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        print("--- Recent Conversations ---")
        res = await session.execute(select(Conversation).order_by(Conversation.created_at.desc()).limit(15))
        convs = res.scalars().all()
        for conv in reversed(convs):
            print(f"[{conv.role.upper()}]: {conv.content[:500]}...\n")

        print("--- Action Logs (search_document) ---")
        res = await session.execute(
            select(ActionLog)
            .where(ActionLog.action_type == "search_document")
            .order_by(ActionLog.created_at.desc())
            .limit(5)
        )
        logs = res.scalars().all()
        for log in logs:
            print(f"Result: {log.result} | Payload: {log.payload}")


if __name__ == "__main__":
    asyncio.run(main())
