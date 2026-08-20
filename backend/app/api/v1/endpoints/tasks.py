from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import create_task, delete_task, get_task, get_tasks, update_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_tasks(session, current_user.id)


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(
    task_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    task = await get_task(session, current_user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskRead)
async def create_new_task(
    task_in: TaskCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await create_task(session, current_user.id, task_in)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_existing_task(
    task_id: UUID,
    task_in: TaskUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await update_task(session, current_user.id, task_id, task_in)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_existing_task(
    task_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    success = await delete_task(session, current_user.id, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}
