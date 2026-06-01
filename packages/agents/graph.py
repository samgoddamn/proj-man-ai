"""LangGraph-orkestrering av agent-pipelinen.

Den linjära kedjan speglar databeroendena:

    discovery → product_manager → architect → engineering
              → scrum_master → qa → health → END

Avvikelse från projektbeskrivningens numrering (avsiktlig):
  * Scrum Master körs EFTER Engineering — sprintplanering kräver task-estimaten.
  * Health körs SIST — riskanalys kräver hela bilden (epics, tasks, sprintar).

Retry/validering bor i llm.py. Statuspublicering bor i status.py via with_status.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    architect_node,
    discovery_node,
    engineering_node,
    health_node,
    product_manager_node,
    qa_node,
    scrum_master_node,
)
from .schemas import AgentState
from .status import with_status

_NODES = {
    "discovery": discovery_node,
    "product_manager": product_manager_node,
    "architect": architect_node,
    "engineering": engineering_node,
    "scrum_master": scrum_master_node,
    "qa": qa_node,
    "health": health_node,
}

_EDGES = [
    ("discovery", "product_manager"),
    ("product_manager", "architect"),
    ("architect", "engineering"),
    ("engineering", "scrum_master"),
    ("scrum_master", "qa"),
    ("qa", "health"),
]


def build_graph():
    """Bygg och kompilera pipeline-grafen."""
    g = StateGraph(AgentState)

    for name, fn in _NODES.items():
        g.add_node(name, with_status(name, fn))

    g.set_entry_point("discovery")
    for src, dst in _EDGES:
        g.add_edge(src, dst)
    g.add_edge("health", END)

    return g.compile()


# Kompilera en gång per process (grafen är tillståndslös; staten skickas per anrop).
GRAPH = build_graph()


async def run_pipeline(state: AgentState) -> AgentState:
    """Kör hela pipelinen och returnera den fullständiga sluttillståndet.

    Anropas av workern (workers/runner.py) efter att ett jobb plockats från Redis.
    Vid SchemaRetryExhausted i någon nod bubblar felet upp hit; with_status har då
    redan publicerat 'failed' för rätt agent, och workern markerar
    agent_runs.status = failed men behåller allt som hann genereras (partial success).
    """
    result = await GRAPH.ainvoke(state)
    return AgentState.model_validate(result)
