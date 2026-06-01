"""Trigga AI-pipelinen och strömma dess status.

POST /projects/{id}/generate
  - Idempotens: blockerar om projektet redan genereras. Vid omkörning på ett
    klart/misslyckat projekt rensas tidigare genererat innehåll (clear_previous)
    innan ett nytt jobb köas — detta är beslutet runner.persist() förutsatte.
  - Skapar en AgentRun, köar jobbet, returnerar run_id direkt (202).

GET /projects/{id}/runs/{run_id}/stream
  - Server-Sent Events med per-nod-status, drivet av Redis pub/sub.
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import ensure_project_access, user_org_ids
from ..dto import GenerateAccepted, GenerateRequest
from ..models import (
    AgentRun,
    Architecture,
    Epic,
    Project,
    ProjectStatus,
    Risk,
    Roadmap,
    RunStatus,
    Sprint,
    User,
)
from ..queue import enqueue_generation, stream_run_status
from ..security import decode_access_token

router = APIRouter(prefix="/projects", tags=["generation"])


async def _clear_previous(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Rensa tidigare genererat innehåll inför en omkörning.

    Epics raderas cascade → stories → tasks. Roadmaps, sprints, architecture och
    risks raderas explicit. Behåller projektets metadata.
    """
    for model in (Epic, Roadmap, Sprint, Architecture, Risk):
        await session.execute(delete(model).where(model.project_id == project_id))


@router.post("/{project_id}/generate", response_model=GenerateAccepted, status_code=202)
async def generate(
    project_id: uuid.UUID,
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
    project: Project = Depends(ensure_project_access),
):
    if project.status == ProjectStatus.generating:
        raise HTTPException(409, "Generering pågår redan för detta projekt")

    await _clear_previous(session, project_id)

    run = AgentRun(project_id=project_id, status=RunStatus.queued)
    session.add(run)
    project.status = ProjectStatus.generating
    await session.flush()

    await enqueue_generation(
        project_id=project_id,
        run_id=run.id,
        brief={
            "name": project.name,
            "description": project.description,
            "target_audience": project.target_audience,
            "business_goals": project.business_goals,
            "budget": project.budget,
            "timeframe": project.timeframe,
        },
        sprint_input=body.model_dump(),
    )
    return GenerateAccepted(run_id=run.id)


@router.get("/{project_id}/runs/{run_id}/stream")
async def stream(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    token: str,
    session: AsyncSession = Depends(get_session),
):
    # EventSource kan inte sätta Authorization-header → token skickas som query-param.
    try:
        user_id = decode_access_token(token)
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "Ogiltig eller utgången token")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Användaren finns inte")

    project = await session.get(Project, project_id)
    if project is None or project.org_id not in await user_org_ids(session, user):
        raise HTTPException(403, "Du har inte åtkomst till detta projekt")

    run = await session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.project_id == project_id)
    )
    if run is None:
        raise HTTPException(404, "Körning hittades inte")

    return StreamingResponse(
        stream_run_status(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
