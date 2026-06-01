"""Per-nod statuspublicering till Redis pub/sub → SSE i frontend.

Noderna själva vet inget om Redis. `with_status` wrappar varje nod och publicerar
running / done / failed på kanalen `run:{run_id}`. API:ets SSE-endpoint prenumererar
på samma kanal och streamar vidare till klienten.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable

import redis.asyncio as redis

from .schemas import AgentState

NodeFn = Callable[[AgentState], Awaitable[dict]]

# Vikt per nod för en grov total progress-uppskattning (summerar till 1.0).
_PROGRESS = {
    "discovery": 0.10,
    "product_manager": 0.20,
    "architect": 0.15,
    "engineering": 0.30,
    "scrum_master": 0.10,
    "qa": 0.10,
    "health": 0.05,
}
_ORDER = list(_PROGRESS)

_pool = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))


def _cumulative(agent: str) -> float:
    idx = _ORDER.index(agent)
    return round(sum(_PROGRESS[a] for a in _ORDER[: idx + 1]), 2)


async def _publish(run_id, agent: str, status: str, error: str | None = None) -> None:
    payload = {
        "agent": agent,
        "status": status,
        "progress": _cumulative(agent) if status == "done" else None,
    }
    if error:
        payload["error"] = error
    await _pool.publish(f"run:{run_id}", json.dumps(payload))


def with_status(agent: str, fn: NodeFn) -> NodeFn:
    """Dekorera en nod så den publicerar sin livscykel till Redis."""

    async def wrapped(state: AgentState) -> dict:
        await _publish(state.run_id, agent, "running")
        try:
            result = await fn(state)
        except Exception as e:  # noqa: BLE001 — vi vill rapportera allt mot UI
            await _publish(state.run_id, agent, "failed", error=str(e))
            raise
        await _publish(state.run_id, agent, "done")
        return result

    wrapped.__name__ = f"status[{agent}]"
    return wrapped
