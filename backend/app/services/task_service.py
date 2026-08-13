from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task
from app.schemas.task import TaskCreate, TaskUpdate


async def get_tasks(session: AsyncSession, user_id: UUID) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task | None:
    stmt = select(Task).where(Task.user_id == user_id, Task.id == task_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_task(session: AsyncSession, user_id: UUID, task_in: TaskCreate) -> Task:
    task = Task(user_id=user_id, **task_in.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task

async def update_task(session: AsyncSession, user_id: UUID, task_id: UUID, task_in: TaskUpdate) -> Task | None:
    task = await get_task(session, user_id, task_id)
    if not task:
        return None
    for k, v in task_in.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    await session.commit()
    await session.refresh(task)
    return task

async def delete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> bool:
    task = await get_task(session, user_id, task_id)
    if not task:
        return False
    await session.delete(task)
    await session.commit()
    return True
