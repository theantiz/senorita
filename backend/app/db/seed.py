import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Contact, MemoryEntry, User


async def seed_db():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        # Create user
        user = User(
            id=uuid.uuid4(),
            name="Test User",
            timezone="UTC",
            autonomy_level=2,
            style_profile={}
        )
        session.add(user)
        await session.flush()

        # Create contact
        contact = Contact(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Alice",
            relationship_type="Friend",
            tone_profile={}
        )
        session.add(contact)

        # Create memory
        memory = MemoryEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            content="Alice likes vintage scarves.",
            category="preference",
            embedding=None
        )
        session.add(memory)

        await session.commit()

        print(f"Inserted User: {user.name} ({user.id})")
        print(f"Inserted Contact: {contact.name} ({contact.id}) linked to User")
        print(f"Inserted Memory: '{memory.content}' ({memory.id}) linked to User")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_db())
