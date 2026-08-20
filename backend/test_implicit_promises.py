import asyncio
import os
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.agents.orchestrator import _implicit_capture_routine
from app.core.config import settings
from app.db.models import Contact, MemoryEntry, Task, User
from app.db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        # Get a user
        res = await session.execute(select(User).limit(1))
        user = res.scalars().first()
        if not user:
            print("No user found")
            return

        # Ensure Rahul is a contact for case 1
        res = await session.execute(select(Contact).where(Contact.user_id == user.id, Contact.name == "Rahul"))
        rahul = res.scalars().first()
        if not rahul:
            rahul = Contact(user_id=user.id, name="Rahul", relationship_type="Friend")
            session.add(rahul)
            await session.commit()

        print(f"Testing for User ID: {user.id}")

        # Helper to run and fetch task
        async def run_test(case_name, msg_text, asst_text):
            print(f"\n--- Running Test: {case_name} ---")
            print(f"User said: {msg_text}")

            # Count tasks before
            res = await session.execute(select(Task).where(Task.user_id == user.id))
            tasks_before = len(res.scalars().all())

            await _implicit_capture_routine(user.id, msg_text, asst_text, "proactive", "UTC")

            # Fetch tasks after
            res = await session.execute(select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc()))
            tasks_after = res.scalars().all()

            if len(tasks_after) > tasks_before:
                new_task = tasks_after[0]
                print("NEW TASK ROW CREATED:")
                print(f"ID: {new_task.id}")
                print(f"Title: {new_task.title}")
                print(f"Due At: {new_task.due_at}")
                print(f"Contact ID: {new_task.contact_id}")
                print(f"Description: {new_task.description}")
            else:
                print("NO NEW TASK CREATED")

        # Test 1: Explicit promise with known contact and relative date
        await run_test(
            "Case 1: Known contact + clear date",
            "I'll follow up with Rahul about the proposal on Friday",
            "Got it. I've noted that down.",
        )

        # Test 2: Ambiguous/Unknown contact
        await run_test(
            "Case 2: Unknown contact", "Remind me to send the files to Bartholomew tomorrow", "I'll remember that."
        )

        # Test 3: Vague statement with no clear date
        await run_test("Case 3: Vague statement", "I should reach out to her sometime", "That sounds like a good idea.")


if __name__ == "__main__":
    asyncio.run(main())
