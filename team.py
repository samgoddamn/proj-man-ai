#!/usr/bin/env python3
"""
Multi-Agent Engineering Team
─────────────────────────────
You prompt the Orchestrator with a goal.
It breaks the work down and dispatches specialized sub-agents in parallel.

Agents
  🏗️  architect  — designs system, writes ARCHITECTURE.md
  🎨  frontend   — React/TypeScript components and hooks
  ⚙️  backend    — API routes, services, data models
  🔍  reviewer   — finds bugs & security issues, writes REVIEW.md

Usage
  python team.py "Build a user auth system with login and signup"
  python team.py --output ./src "Add a dark-mode toggle"
  python team.py                             # interactive mode
"""

import anthropic
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ── Shared state ──────────────────────────────────────────────────────────────

client = anthropic.Anthropic()
output_dir: Path = Path("./team_output").resolve()
feature_slug: str = "feature"  # sätts från --feature; används för doc-sökvägar

# ── Projektkontext (vävs in i varje agents prompt) ───────────────────────────

PROJECT_CONTEXT = """\
## Project context — you work INSIDE an existing monorepo, not a blank slate

Repo layout (paths are relative to the output root, which is the repo root):
- apps/web/        Next.js 16 (App Router) + React 19 + TypeScript + Tailwind.
                   Client-side fetching via apps/web/lib/api.ts (typed fetch that
                   attaches the JWT). Auth via apps/web/lib/auth.ts + useRequireAuth.
                   Reusable UI in apps/web/components/ui/primitives.tsx.
- apps/api/        FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async).
                   Routers: apps/api/app/routers/<resource>.py (registered in main.py)
                   DTOs:    apps/api/app/dto.py
                   Models:  apps/api/app/models.py
                   Session dep: apps/api/app/db.py (get_session)
                   Auth deps:   apps/api/app/deps.py (get_current_user, ensure_project_access)
- packages/agents/ LangGraph-pipeline. Do NOT modify unless the task is about it.
- alembic/         DB-migrationer. Nya/ändrade modeller kräver en migration i alembic/versions/.

Rules for everyone:
- Read neighbouring files first (read_file / list_directory) and MATCH existing
  conventions and imports. Do not invent a parallel style.
- Write each file under its correct package path. Use relative paths from the repo root.
- NEVER overwrite root ARCHITECTURE.md, README.md or CLAUDE.md.
- Skip node_modules/.next/.venv — never read or write there.
"""

# ── File tools (every agent gets these) ──────────────────────────────────────

FILE_TOOLS = [
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Parent directories are created automatically. "
            "Use relative paths, e.g. 'components/Auth/LoginForm.tsx'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read an existing file. Use this to check what was already written.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path (default '.' = output root)",
                    "default": ".",
                },
            },
            "required": [],
        },
    },
]


def _write_file(path: str, content: str) -> str:
    full = output_dir / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"Created {path} ({len(content)} bytes)"


def _read_file(path: str) -> str:
    full = output_dir / path
    return full.read_text(encoding="utf-8") if full.exists() else f"Error: {path} not found"


# Tunga mappar som aldrig ska listas/genomsökas (sparar tokens, undviker brus).
_IGNORE_DIRS = {"node_modules", ".next", ".git", ".venv", "venv", "__pycache__", "team_output"}


def _list_directory(path: str = ".") -> str:
    full = output_dir / path
    if not full.exists():
        return f"Error: {path} not found"
    entries = sorted(full.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [
        ("  " if e.is_file() else "D ") + e.name
        for e in entries
        if e.name not in _IGNORE_DIRS
    ]
    return "\n".join(lines) if lines else "(empty)"


_FILE_HANDLERS = {
    "write_file": lambda i: _write_file(i["path"], i["content"]),
    "read_file": lambda i: _read_file(i["path"]),
    "list_directory": lambda i: _list_directory(i.get("path", ".")),
}


def execute_file_tool(name: str, inp: dict) -> str:
    try:
        return _FILE_HANDLERS[name](inp)
    except Exception as e:
        return f"Error: {e}"


# ── Agent profiles ────────────────────────────────────────────────────────────

AGENTS = {
    "architect": {
        "emoji": "🏗️",
        "description": "Plans system design, file structure, API contracts, and data models",
        "system": """\
You are the Architect. You design before anyone builds.

Responsibilities:
- Decide what files are needed and where they live (using the monorepo layout)
- Define API contracts: FastAPI endpoint paths + Pydantic request/response shapes
- Design SQLAlchemy models and the matching Alembic migration outline
- Design the frontend pieces (pages, components, api-client additions)
- Write the design plan to docs/plans/<feature-slug>.md

Rules:
- Write the plan document ONLY — don't implement features
- Be concise and specific; reference real paths (apps/api/app/..., apps/web/...)
- NEVER write to the root ARCHITECTURE.md — your plan goes in docs/plans/<feature-slug>.md
- Write the plan last, after thinking through the design
""",
    },
    "frontend": {
        "emoji": "🎨",
        "description": "Builds React components, custom hooks, and UI logic",
        "system": """\
You are the Frontend Developer. You build production-quality React/TypeScript UI.

Responsibilities:
- Write React functional components with full TypeScript types
- Create custom hooks for state and side effects
- Build accessible, responsive UIs with proper loading and error states
- Check ARCHITECTURE.md first if it exists — follow the plan

Conventions (this repo's real paths):
- Pages       → apps/web/app/<route>/page.tsx  ("use client" + useRequireAuth för skyddade sidor)
- Components   → apps/web/components/<Feature>/...
- Hooks/utils  → apps/web/lib/use<Name>.ts
- API-anrop    → använd apps/web/lib/api.ts (lägg till metoder där, bifogar JWT automatiskt)
- UI           → återanvänd apps/web/components/ui/primitives.tsx (Button, Card, Field, Input…)

Rules:
- Never skip error states or loading states
- Keep each file focused — no 500-line components
- Use TypeScript strictly — no `any`
- Match the existing client-side fetch-pattern; bygg inte en parallell datahämtning
""",
    },
    "backend": {
        "emoji": "⚙️",
        "description": "Builds API routes, services, and data access layers",
        "system": """\
You are the Backend Developer. You build robust, secure FastAPI (Python 3.12) code.

Responsibilities:
- Add/extend FastAPI routers (APIRouter) in apps/api/app/routers/<resource>.py
- Define request/response DTOs in apps/api/app/dto.py (Pydantic v2; from_attributes
  för ORM-serialisering)
- Add SQLAlchemy 2.0 models to apps/api/app/models.py when persistence is needed,
  AND a matching Alembic migration in alembic/versions/ (följ formatet i 0002_auth.py)
- Use the get_session dependency (apps/api/app/db.py) and auth deps
  (apps/api/app/deps.py: get_current_user, ensure_project_access) to protect and
  org-scope routes
- Register new routers in apps/api/app/main.py
- Check docs/plans/<feature-slug>.md first if it exists — follow the plan

Conventions (this repo's real paths):
- Routers → apps/api/app/routers/<resource>.py
- DTOs    → apps/api/app/dto.py
- Models  → apps/api/app/models.py  (+ alembic/versions/ migration)

Rules:
- Async SQLAlchemy throughout (matcha mönstren i befintliga routrar/modeller)
- Validate all inputs with Pydantic — never trust user data
- Return consistent error shapes via HTTPException
- No secrets hardcoded — use os.environ
""",
    },
    "reviewer": {
        "emoji": "🔍",
        "description": "Reviews code for bugs, security issues, and improvements",
        "system": """\
You are the Code Reviewer. You find real bugs, not style nitpicks.

Responsibilities:
- Review the files the other agents just created/changed for THIS feature (the
  orchestrator lists them in your context). Read those files with read_file.
- Identify: bugs, security vulnerabilities, missing validation, race conditions, unhandled errors
- Write findings to docs/reviews/<feature-slug>.md, organized by severity: Critical / Major / Minor

Rules:
- Only review this feature's files — do NOT crawl the whole repo, node_modules or .next
- Quote the specific code that has a problem
- Explain *why* it's a problem
- For Critical/Major issues, show the fix
- Don't rewrite files — write docs/reviews/<feature-slug>.md only
- Skip pure style/naming preferences unless they cause confusion
""",
    },
}

# ── Sub-agent runner ──────────────────────────────────────────────────────────


def run_subagent(role: str, task: str, context: str = "") -> str:
    """Run a sub-agent to completion and return its final summary."""
    profile = AGENTS.get(role)
    if not profile:
        return f"Error: unknown role '{role}'. Choose from: {', '.join(AGENTS)}"

    emoji = profile["emoji"]
    print(f"  {emoji}  [{role}] ▶  {task[:70]}{'…' if len(task) > 70 else ''}")

    system = (
        profile["system"]
        + "\n\n"
        + PROJECT_CONTEXT
        + f"\n\nFeature slug for doc paths: `{feature_slug}` "
        f"(plan → docs/plans/{feature_slug}.md, review → docs/reviews/{feature_slug}.md)"
    )
    if context:
        system += f"\n\n## Context from orchestrator\n{context}"

    messages = [{"role": "user", "content": task}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            tools=FILE_TOOLS,
            messages=messages,
        )

        # Done — extract final text
        if response.stop_reason == "end_turn":
            summary = next((b.text for b in response.content if b.type == "text"), "(no summary)")
            print(f"  {emoji}  [{role}] ✓  Done")
            return summary

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_blocks:
            return next((b.text for b in response.content if b.type == "text"), "(done)")

        # Execute all tool calls and collect results
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tb in tool_blocks:
            result = execute_file_tool(tb.name, tb.input)
            if tb.name == "write_file":
                print(f"  {emoji}  [{role}]    wrote {tb.input['path']}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})


# ── Orchestrator ──────────────────────────────────────────────────────────────

DISPATCH_TOOL = {
    "name": "dispatch_agent",
    "description": (
        "Assign a task to a specialist sub-agent. "
        "Call this multiple times in a single response to run agents in parallel. "
        "All agents share the same output directory and can read each other's files.\n\n"
        "Available roles:\n"
        + "\n".join(
            f"  {p['emoji']} {role}: {p['description']}"
            for role, p in AGENTS.items()
        )
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": list(AGENTS.keys()),
                "description": "Which specialist to use",
            },
            "task": {
                "type": "string",
                "description": (
                    "Clear, specific task for this agent. "
                    "Include what files to create and any important constraints."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional context this agent needs: design decisions, "
                    "data shapes, constraints from other agents."
                ),
            },
        },
        "required": ["role", "task"],
    },
}

_AGENT_LIST = "\n".join(
    f"- **{role}** ({p['emoji']}): {p['description']}" for role, p in AGENTS.items()
)

ORCHESTRATOR_SYSTEM = f"""\
You are the Engineering Lead. You receive feature requests and coordinate a team of specialists.

Your team:
{_AGENT_LIST}

How to work:
1. Think through what the feature needs (use thinking before dispatching)
2. Dispatch agents with dispatch_agent — you can call it multiple times in one response to run in parallel
3. Typical flow for complex features:
   - architect first (system design + ARCHITECTURE.md)
   - then frontend + backend simultaneously
   - reviewer last (after all code is written)
4. For simple features, skip architect and dispatch directly to frontend/backend
5. When all work is done, summarize what was built

Rules:
- Be decisive — dispatch immediately, don't ask clarifying questions unless truly stuck
- Agents share the output directory; they can read each other's files
- Give each agent a specific, actionable task — not vague goals
"""


def run_orchestrator(goal: str) -> str:
    """Run the orchestrator until it finishes, then return the summary."""
    print(f"\n🎯  {goal}\n{'─' * 60}")
    orchestrator_system = (
        ORCHESTRATOR_SYSTEM
        + "\n\n"
        + PROJECT_CONTEXT
        + f"\n\nThis feature's slug is `{feature_slug}`. Pass it to agents so the "
        f"architect writes docs/plans/{feature_slug}.md and the reviewer writes "
        f"docs/reviews/{feature_slug}.md. Tell the reviewer exactly which files were created."
    )
    messages = [{"role": "user", "content": goal}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=orchestrator_system,
            tools=[DISPATCH_TOOL],
            messages=messages,
        )

        # Orchestrator finished
        if response.stop_reason == "end_turn":
            return next((b.text for b in response.content if b.type == "text"), "(done)")

        dispatch_calls = [b for b in response.content if b.type == "tool_use"]
        if not dispatch_calls:
            return next((b.text for b in response.content if b.type == "text"), "(done)")

        messages.append({"role": "assistant", "content": response.content})

        # Run sub-agents — parallel when multiple dispatches, sequential for one
        if len(dispatch_calls) > 1:
            print(f"\n  ⚡  Running {len(dispatch_calls)} agents in parallel…\n")
            results: dict[str, str] = {}
            with ThreadPoolExecutor(max_workers=len(dispatch_calls)) as pool:
                future_to_id = {
                    pool.submit(
                        run_subagent,
                        call.input["role"],
                        call.input["task"],
                        call.input.get("context", ""),
                    ): call.id
                    for call in dispatch_calls
                }
                for future, call_id in future_to_id.items():
                    results[call_id] = future.result()
            tool_results = [
                {"type": "tool_result", "tool_use_id": call.id, "content": results[call.id]}
                for call in dispatch_calls
            ]
        else:
            call = dispatch_calls[0]
            result = run_subagent(
                call.input["role"],
                call.input["task"],
                call.input.get("context", ""),
            )
            tool_results = [
                {"type": "tool_result", "tool_use_id": call.id, "content": result}
            ]

        messages.append({"role": "user", "content": tool_results})


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-agent engineering team — orchestrator + specialists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {p['emoji']}  {role:<12} {p['description']}" for role, p in AGENTS.items()
        ),
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="Feature to build (omit for interactive mode)",
    )
    parser.add_argument(
        "--output", "-o",
        default="./team_output",
        help="Output directory (default: ./team_output; sätt till repo-roten för att "
        "skriva direkt in i monorepot)",
    )
    parser.add_argument(
        "--feature", "-f",
        default="feature",
        help="Kort slug för featuren (styr doc-sökvägar: docs/plans/<slug>.md m.fl.)",
    )
    args = parser.parse_args()

    global output_dir, feature_slug
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_slug = args.feature
    print(f"Output: {output_dir}")
    print(f"Feature: {feature_slug}")

    if args.goal:
        summary = run_orchestrator(args.goal)
        print(f"\n{'─' * 60}\n{summary}\n{'─' * 60}")
        return

    # Interactive mode
    print("\nMulti-agent team ready. Type a feature goal (or 'quit').\n")
    while True:
        try:
            goal = input("🎯  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if goal.lower() in ("quit", "exit", "q"):
            break
        if not goal:
            continue
        summary = run_orchestrator(goal)
        print(f"\n{'─' * 60}\n{summary}\n{'─' * 60}\n")


if __name__ == "__main__":
    main()
