"""Worker: konsumerar genereringsjobb från Redis, kör pipelinen, persisterar resultat.

Flöde per jobb:
  1. BLPOP nästa jobb från kön `gen:queue`.
  2. Markera AgentRun=running, Project.status=generating.
  3. Bygg AgentState och kör run_pipeline (LangGraph). with_status strömmar
     per-nod-status till Redis pub/sub under tiden → SSE i frontend.
  4. Persistera Draft-output → SQLAlchemy-rader i EN transaktion. Servern sätter
     id/order/board_order; modellen genererar dem aldrig.
  5. Project.status=ready, AgentRun=succeeded.

Vid fel: behåll allt som hann genereras (partial success), markera Project.status
=failed och AgentRun=failed med felmeddelandet. with_status har redan publicerat
'failed' för rätt agent, så frontendens checklista visar var det brast.

Importbanor förutsätter att `packages/agents` och `apps/api/app` ligger på
PYTHONPATH (editable installs i monorepot) → importerbara som `agents` resp. `app`.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone

import redis.asyncio as redis
from sqlalchemy import update

from agents.graph import run_pipeline
from agents.schemas import AgentState, ProjectBrief, SprintInput
from app.db import session_scope
from app.models import (
    AgentRun,
    Architecture,
    Epic,
    Project,
    ProjectStatus,
    Risk,
    Roadmap,
    RunStatus,
    Sprint,
    Task,
    UserStory,
)

QUEUE_KEY = "gen:queue"
_BLPOP_TIMEOUT = 30  # seconds; reconnects naturally each cycle
_redis = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    socket_timeout=_BLPOP_TIMEOUT + 5,
    socket_connect_timeout=5,
)


# --------------------------------------------------------------------------- #
# Draft → DB-mappning
# --------------------------------------------------------------------------- #


async def persist(session, project_id, state: AgentState) -> None:
    """Mappa pipeline-output till rader. Anropas inom en transaktion (session_scope).

    Förutsätter att tidigare genererat innehåll redan rensats (vid omkörning) — se
    clear_previous(). Ordning och beroenden hanteras genom att bygga upp lookup-
    tabeller (fas→roadmap_id, epic_title→epic, task_title→Task) allt eftersom.
    """
    # --- Roadmap: fasnummer → roadmap_id (för att länka epics) ---
    phase_to_roadmap: dict[int, "Roadmap"] = {}
    if state.plan:
        for order, ph in enumerate(state.plan.roadmap):
            rm = Roadmap(
                project_id=project_id, phase=ph.phase, title=ph.title,
                summary=ph.summary, order=order,
            )
            session.add(rm)
            phase_to_roadmap[ph.phase] = rm
        await session.flush()  # tilldela roadmap-id

    # --- Epics: titel → Epic (för att länka breakdowns) ---
    title_to_epic: dict[str, "Epic"] = {}
    if state.plan:
        for order, ep in enumerate(state.plan.epics):
            rm = phase_to_roadmap.get(ep.phase)
            epic = Epic(
                project_id=project_id,
                roadmap_id=rm.id if rm else None,
                title=ep.title, description=ep.description,
                priority=ep.priority.value, business_value=ep.business_value,
                order=order,
            )
            session.add(epic)
            title_to_epic[ep.title] = epic
        await session.flush()  # tilldela epic-id

    # --- Stories + Tasks (från Engineering fan-out): titel → Task (för sprint-länk) ---
    title_to_task: dict[str, "Task"] = {}
    board_pos = 0.0
    for bd in state.breakdowns:
        epic = title_to_epic.get(bd.epic_title)
        if epic is None:
            # echo-fältet matchade inget epic — hoppa hellre än att tappa data tyst
            state.errors.append(f"Breakdown för okänt epic: {bd.epic_title!r}")
            continue
        for s_order, st in enumerate(bd.stories):
            story = UserStory(
                epic_id=epic.id, role=st.role, want=st.want, so_that=st.so_that,
                acceptance_criteria=list(st.acceptance_criteria), order=s_order,
            )
            session.add(story)
            await session.flush()  # tilldela story-id innan tasks
            for tk in st.tasks:
                board_pos += 1.0
                task = Task(
                    story_id=story.id, title=tk.title, description=tk.description,
                    type=tk.type.value, estimate=tk.estimate, board_order=board_pos,
                )
                session.add(task)
                title_to_task.setdefault(tk.title, task)
    await session.flush()  # tilldela task-id

    # --- Sprintar: skapa rader + koppla tasks via task_titles ---
    if state.sprint_plan:
        weeks = state.sprint_input.sprint_length_weeks
        cursor = date.today()
        for order, sp in enumerate(state.sprint_plan.sprints):
            start = cursor
            end = start + timedelta(weeks=weeks)
            sprint = Sprint(
                project_id=project_id, name=sp.name, goal=sp.goal,
                capacity_points=sp.capacity_points, start_date=start, end_date=end,
                order=order,
            )
            session.add(sprint)
            await session.flush()  # tilldela sprint-id
            for title in sp.task_titles:
                task = title_to_task.get(title)
                if task is not None:
                    task.sprint_id = sprint.id
            cursor = end

    # --- Arkitektur (en rad per projekt) ---
    if state.architecture:
        session.add(
            Architecture(
                project_id=project_id,
                stack=[s.model_dump() for s in state.architecture.stack],
                data_model=[d.model_dump() for d in state.architecture.data_model],
                api_design=[a.model_dump() for a in state.architecture.api_design],
                rationale=state.architecture.rationale,
            )
        )

    # --- Risker ---
    if state.health:
        for r in state.health.risks:
            session.add(
                Risk(
                    project_id=project_id, title=r.title, description=r.description,
                    severity=r.severity.value, affected_epics=list(r.affected_epics),
                    recommendation=r.recommendation,
                )
            )


# --------------------------------------------------------------------------- #
# Jobbhantering
# --------------------------------------------------------------------------- #


async def handle_job(job: dict) -> None:
    project_id = job["project_id"]
    run_id = job["run_id"]
    now = datetime.now(timezone.utc)

    async with session_scope() as s:
        await s.execute(
            update(Project).where(Project.id == project_id).values(status=ProjectStatus.generating)
        )
        await s.execute(
            update(AgentRun).where(AgentRun.id == run_id).values(
                status=RunStatus.running, started_at=now
            )
        )

    state = AgentState(
        project_id=project_id,
        run_id=run_id,
        brief=ProjectBrief(**job["brief"]),
        sprint_input=SprintInput(**job["sprint_input"]),
    )

    try:
        result = await run_pipeline(state)
        async with session_scope() as s:
            await persist(s, project_id, result)
            await s.execute(
                update(Project).where(Project.id == project_id).values(status=ProjectStatus.ready)
            )
            await s.execute(
                update(AgentRun).where(AgentRun.id == run_id).values(
                    status=RunStatus.succeeded, finished_at=datetime.now(timezone.utc)
                )
            )
    except Exception as e:  # noqa: BLE001
        async with session_scope() as s:
            await s.execute(
                update(Project).where(Project.id == project_id).values(status=ProjectStatus.failed)
            )
            await s.execute(
                update(AgentRun).where(AgentRun.id == run_id).values(
                    status=RunStatus.failed, error=str(e),
                    finished_at=datetime.now(timezone.utc),
                )
            )
        raise


async def main() -> None:
    print("worker: väntar på jobb på", QUEUE_KEY)
    while True:
        try:
            result = await _redis.blpop(QUEUE_KEY, timeout=_BLPOP_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            print(f"worker: Redis-anslutningsfel: {e}. Försöker igen om 5s...")
            await asyncio.sleep(5)
            continue
        if result is None:
            continue  # blpop-timeout, ingen loop-paus behövs
        _, raw = result
        job = json.loads(raw)
        try:
            await handle_job(job)
        except Exception as e:  # noqa: BLE001 — logga och fortsätt med nästa jobb
            print(f"worker: jobb {job.get('run_id')} misslyckades: {e}")


if __name__ == "__main__":
    asyncio.run(main())
