"""Redis-kö (enqueue av genereringsjobb) + SSE-prenumeration på run-status.

Workern (workers/runner.py) gör BLPOP på samma QUEUE_KEY och publicerar per-nod-
status på kanalen `run:{run_id}` via packages/agents/status.py. SSE-endpointen
prenumererar här och streamar vidare till klienten.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as redis

QUEUE_KEY = "gen:queue"
_redis = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    socket_timeout=None,
    socket_connect_timeout=5,
)

# Agenter i exekveringsordning — klienten vet att körningen är klar när 'health'
# rapporterar done, eller direkt vid någon 'failed'.
TERMINAL_AGENT = "health"


async def enqueue_generation(*, project_id: UUID, run_id: UUID, brief: dict, sprint_input: dict) -> None:
    job = {
        "project_id": str(project_id),
        "run_id": str(run_id),
        "brief": brief,
        "sprint_input": sprint_input,
    }
    await _redis.rpush(QUEUE_KEY, json.dumps(job))


async def stream_run_status(run_id: UUID) -> AsyncIterator[str]:
    """Yield:ar SSE-formaterade rader för en körnings status tills den avslutas."""
    pubsub = _redis.pubsub()
    await pubsub.subscribe(f"run:{run_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()
            yield f"data: {data}\n\n"

            payload = json.loads(data)
            done = payload.get("agent") == TERMINAL_AGENT and payload.get("status") == "done"
            failed = payload.get("status") == "failed"
            if done or failed:
                yield "event: end\ndata: {}\n\n"
                break
    finally:
        await pubsub.unsubscribe(f"run:{run_id}")
        await pubsub.aclose()
