import asyncio
import logging
from db.session import get_db
from db.models import Integration
from sqlalchemy import select
from integrations.base import get_adapter

logging.basicConfig(level=logging.INFO)

async def main():
    try:
        # get_db is a generator, so we need to iterate it
        async for session in get_db():
            stmt = select(Integration).where(Integration.provider == "gmail")
            result = await session.execute(stmt)
            integrations = result.scalars().all()
            
            adapter = get_adapter("gmail")
            for i in integrations:
                try:
                    await adapter.refresh_access_token(i)
                    print("Refresh succeeded.")
                except Exception as e:
                    print(f"Exception caught: {e}")
            break
    except Exception as ex:
        print(f"Outer exception: {ex}")

asyncio.run(main())
