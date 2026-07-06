
# Copilot Instructions for AI Project Manager (repo-specific)

Short guide for GitHub Copilot / automated suggestions when editing this repository.

Overview
--------
- Purpose: Provide concise, actionable rules so Copilot's suggestions align with repository
  conventions, security posture, and review expectations.

Quick Git rules
---------------
- Never commit directly to `main`. Create a branch from an up-to-date `main` before editing.
- Branch prefixes: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/` (e.g. `feat/openai-streaming`).
- Commit messages should be imperative and concise. AI-assisted commits include this trailer:

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- Open a PR for every change and do not merge without a human reviewer.

PR & Verification checklist (examples)
-------------------------------------
- Backend: run `python -m py_compile` for changed files and run unit tests targeting modified modules.
- Frontend: in `apps/web` run `npx tsc --noEmit` then `npm run build` to catch typing and bundling issues.
- Database models: if you add or change SQLAlchemy models, also add an Alembic migration under
  `alembic/versions/`. Example migration check:

```bash
alembic revision --autogenerate -m "add example field"
alembic upgrade --sql head  # inspect generated DDL
```

Security & secrets
------------------
- Never hardcode secrets or credentials. Use `os.environ` and documented env vars.
- If a suggestion would log or return sensitive fields, reject it and prefer redaction.

Backend rules and examples (`apps/api`)
-------------------------------------
- Protect routes with dependencies:

```py
@router.get("/projects/{id}")
async def get_project(id: UUID, user=Depends(get_current_user)):
    project = await repo.get_project(id)
    ensure_project_access(user, project)
    return project
```

- Use Pydantic DTOs for request validation; never read raw `request.json()` for business data.

Example DTO usage (`apps/api/app/dto.py`):

```py
class ProjectCreate(BaseModel):
    name: str
    description: str | None
    target_audience: str | None

@router.post("/projects")
async def create_project(dto: ProjectCreate, user=Depends(get_current_user)):
    ...
```

- Async SQLAlchemy only in async endpoints. If changing DB access patterns, prefer `async_session`.

Agent pipeline & LLM usage (`packages/agents`, `workers`)
------------------------------------------------------
- Always request structured output from the provider (response_format / tool call) and validate with
  Pydantic schemas. Example Pydantic schema for an agent response:

```py
class RoadmapPhase(BaseModel):
    phase: int
    title: str
    summary: str

response_format = {
    "type": "json_schema",
    "json_schema": RoadmapPhase.model_json_schema()
}
```

- Log every node invocation in `agent_steps` with timing, input/output tokens, and the raw response.
- Publish progress events to Redis pub/sub using the key `run:{run_id}` so the API can push SSEs.
- Never accept server-owned fields (e.g., `id`, `order`, `org_id`) from LLM output — map drafts
  to DB rows server-side and assign those fields explicitly.
- On schema validation errors: retry once or twice, injecting the validation error into the prompt; if
  still invalid, mark `agent_runs.status = failed` and persist the raw output for debugging.

Example SSE payload produced by worker:

```json
{"agent":"engineering","status":"running","progress":0.6,"step_id":"..."}
```

Frontend rules (`apps/web`)
--------------------------
- Gate protected pages with `useRequireAuth` and wait for `ready` before rendering any user-specific data.

Example (React/Next):

```tsx
const Page = () => {
  const { ready, user } = useRequireAuth()
  if (!ready) return <Loading />
  return <MainView user={user} />
}
```

- Use `apps/web/lib/api.ts` for all backend calls (it attaches JWT). Avoid ad-hoc `fetch()` calls that skip
  the shared client logic.
- Keep TypeScript strict. If a quick fix would use `any`, prefer creating a small DTO in `lib/types.ts` instead.

Code quality & review guidance
-----------------------------
- Classify findings as **Important** vs **Nit**. Important items must include `file:line` evidence.
- Limit Nits to five per review; if there are more, summarize with "plus N similar".

Examples and small patterns to prefer
-----------------------------------
- Prefer small, well-typed DTOs over passing large dicts through layers.
- Use `asyncio.Semaphore` to limit parallel fan-out in `engineering` agent when generating per-epic tasks.

When Copilot is unsure
----------------------
- If a suggested change touches authentication, DB schema, or LLM prompts, create a draft PR and add
  `WIP:` in the title for human review rather than committing directly.

Where to read more
------------------
- `CLAUDE.md` — repo conventions
- `REVIEW.md` — review instructions and what to flag
- `ARCHITECTURE.md` — architecture and agent ordering rationale

Next steps
----------
- Use these expanded rules for suggestion context. I can also generate a Swedish translation
  or open a PR for these changes if you want.

