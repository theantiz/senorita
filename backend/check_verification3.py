import asyncio
from sqlalchemy import select, text
from app.db.session import async_session_factory

async def main():
    async with async_session_factory() as session:
        # Check all action logs in last hour
        res = await session.execute(text("SELECT action_type, payload, result FROM action_log ORDER BY created_at DESC LIMIT 20"))
        print("--- Last 20 Action Logs ---")
        for row in res:
            print(row)

        print("\n--- Any Documents? ---")
        res = await session.execute(text("SELECT id, filename, source FROM documents"))
        docs = res.fetchall()
        for doc in docs:
            print(doc)
            
        print("\n--- Any Chunks? ---")
        res = await session.execute(text("SELECT document_id, chunk_index, chunk_text FROM document_chunks LIMIT 5"))
        for chunk in res:
            print(chunk)

if __name__ == "__main__":
    asyncio.run(main())
