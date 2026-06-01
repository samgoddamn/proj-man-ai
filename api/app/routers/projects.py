"""Projekt-CRUD och full hierarki-läsning."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..deps import ensure_project_access, get_current_user, primary_org_id, user_org_ids
from ..dto import ArchitectureOut, ProjectCreate, ProjectDetail, ProjectOut
from ..models import Architecture, Epic, Project, User, UserStory

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = Project(**body.model_dump(), org_id=await primary_org_id(session, user))
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    org_ids = await user_org_ids(session, user)
    rows = await session.scalars(
        select(Project).where(Project.org_id.in_(org_ids)).order_by(Project.created_at.desc())
    )
    return list(rows)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: Project = Depends(ensure_project_access),
):
    project = await session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.roadmaps),
            selectinload(Project.sprints),
            selectinload(Project.risks),
            selectinload(Project.epics)
            .selectinload(Epic.stories)
            .selectinload(UserStory.tasks),
        )
    )
    if project is None:
        raise HTTPException(404, "Projekt hittades inte")

    architecture = await session.scalar(
        select(Architecture).where(Architecture.project_id == project_id)
    )

    detail = ProjectDetail.model_validate(project)
    if architecture:
        detail.architecture = ArchitectureOut.model_validate(architecture)
    return detail
