"""Kanban: hämta board grupperad per status, och uppdatera enskild task."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import ensure_project_access, get_current_user, user_org_ids
from ..dto import BoardColumn, BoardOut, TaskOut, TaskPatch
from ..models import Epic, Project, Sprint, Task, TaskStatus, User, UserStory

router = APIRouter(tags=["board"])

# Kolumnordning som UI:t förväntar sig.
_COLUMNS = [
    TaskStatus.backlog,
    TaskStatus.todo,
    TaskStatus.in_progress,
    TaskStatus.review,
    TaskStatus.done,
]


@router.get("/projects/{project_id}/board", response_model=BoardOut)
async def get_board(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: Project = Depends(ensure_project_access),
):
    # Task → Story → Epic → Project; sortera inom kolumn på board_order.
    rows = await session.scalars(
        select(Task)
        .join(UserStory, Task.story_id == UserStory.id)
        .join(Epic, UserStory.epic_id == Epic.id)
        .where(Epic.project_id == project_id)
        .order_by(Task.board_order)
    )
    tasks = list(rows)
    grouped: dict[TaskStatus, list[Task]] = {c: [] for c in _COLUMNS}
    for t in tasks:
        grouped[t.status].append(t)

    return BoardOut(
        columns=[
            BoardColumn(status=c, tasks=[TaskOut.model_validate(t) for t in grouped[c]])
            for c in _COLUMNS
        ]
    )


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: uuid.UUID,
    body: TaskPatch,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task hittades inte")

    # Verifiera ägarskap: task → story → epic → project.org_id måste vara användarens.
    org_id = await session.scalar(
        select(Project.org_id)
        .join(Epic, Epic.project_id == Project.id)
        .join(UserStory, UserStory.epic_id == Epic.id)
        .where(UserStory.id == task.story_id)
    )
    if org_id not in await user_org_ids(session, user):
        raise HTTPException(403, "Du har inte åtkomst till denna task")

    fields = body.model_dump(exclude_unset=True)
    if "sprint_id" in fields and fields["sprint_id"] is not None:
        sprint = await session.get(Sprint, fields["sprint_id"])
        if sprint is None:
            raise HTTPException(422, "Angiven sprint finns inte")

    for key, value in fields.items():
        setattr(task, key, value)
    await session.flush()
    await session.refresh(task)
    return task
