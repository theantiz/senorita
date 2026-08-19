import asyncio
from sqlalchemy import select, text
from app.db.session import async_session_factory
from app.db.models import ActionLog, Conversation

async def main():
    async with async_session_factory() as session:
        # Check action logs for document uploads or deletions
        res = await session.execute(
            select(ActionLog).order_by(ActionLog.created_at.desc()).limit(10)
        )
        logs = res.scalars().all()
        print("--- Recent Action Logs ---")
        for log in logs:
            print(f"[{log.created_at}] {log.action_type}: {log.details}")

        print("\n--- Recent Conversations ---")
        res = await session.execute(text("SELECT * FROM conversations ORDER BY created_at DESC LIMIT 5"))
        for row in res:
            print(row)
            
        print("\n--- Documents Left ---")
        res = await session.execute(text("SELECT id, filename FROM documents"))
        for row in res:
            print(row)

if __name__ == "__main__":
    asyncio.run(main())
