"""Agent-noder. En funktion per agent; var och en tar AgentState och returnerar
en partiell state-uppdatering som LangGraph mergar in.

Noderna är medvetet tunna: de renderar en prompt (prompts/), anropar
call_structured (llm.py) och returnerar resultatet. All retry/validering bor i
llm.py; all statuspublicering bor i status.py.
"""

from __future__ import annotations

import asyncio

from ..llm import call_structured, get_llm
from ..prompts import render
from ..schemas import (
    AgentState,
    ArchitectureDraft,
    DiscoveryOutput,
    EpicBreakdown,
    EpicDraft,
    HealthReport,
    ProductPlan,
    SprintPlan,
    TestPlan,
)


async def discovery_node(state: AgentState) -> dict:
    out = await call_structured(
        get_llm(),
        system=render("discovery_system"),
        user=render("discovery_user", brief=state.brief),
        schema=DiscoveryOutput,
    )
    return {"discovery": out}


async def product_manager_node(state: AgentState) -> dict:
    out = await call_structured(
        get_llm(),
        system=render("pm_system"),
        user=render("pm_user", brief=state.brief, discovery=state.discovery),
        schema=ProductPlan,
    )
    return {"plan": out}


async def architect_node(state: AgentState) -> dict:
    out = await call_structured(
        get_llm(),
        system=render("architect_system"),
        user=render(
            "architect_user", brief=state.brief, discovery=state.discovery, plan=state.plan
        ),
        schema=ArchitectureDraft,
    )
    return {"architecture": out}


async def engineering_node(state: AgentState) -> dict:
    """Fan-out: en strukturerad nedbrytning per epic, parallellt med semafor."""
    sem = asyncio.Semaphore(4)
    llm = get_llm()

    async def one(epic: EpicDraft) -> EpicBreakdown:
        async with sem:
            return await call_structured(
                llm,
                system=render("engineering_system"),
                user=render(
                    "engineering_user",
                    brief=state.brief,
                    architecture=state.architecture,
                    epic=epic,
                ),
                schema=EpicBreakdown,
            )

    breakdowns = await asyncio.gather(*(one(e) for e in state.plan.epics))
    return {"breakdowns": list(breakdowns)}


async def scrum_master_node(state: AgentState) -> dict:
    # Kapacitet beräknas deterministiskt i kod och matas in i prompten.
    out = await call_structured(
        get_llm(),
        system=render("scrum_system"),
        user=render(
            "scrum_user",
            sprint_input=state.sprint_input,
            capacity=state.sprint_input.capacity_points,
            breakdowns=state.breakdowns,
            epics=state.plan.epics,
        ),
        schema=SprintPlan,
    )
    return {"sprint_plan": out}


async def qa_node(state: AgentState) -> dict:
    out = await call_structured(
        get_llm(),
        system=render("qa_system"),
        user=render("qa_user", breakdowns=state.breakdowns),
        schema=TestPlan,
    )
    return {"test_plan": out}


async def health_node(state: AgentState) -> dict:
    # Health ser hela bilden för att resonera om tvärgående beroenden.
    out = await call_structured(
        get_llm(),
        system=render("health_system"),
        user=render(
            "health_user",
            plan=state.plan,
            breakdowns=state.breakdowns,
            sprint_plan=state.sprint_plan,
        ),
        schema=HealthReport,
    )
    return {"health": out}
