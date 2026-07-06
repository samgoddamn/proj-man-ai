#!/usr/bin/env python3
"""
Multi-Agent Engineering Team
-----------------------------
You prompt the Orchestrator with a goal.
It breaks the work down and dispatches specialized sub-agents.

Agents
  architect  - designs system, writes plan docs
  frontend   - React/TypeScript components and hooks
  backend    - API routes, services, data models
  reviewer   - finds bugs and security issues, writes review docs

Usage
  python3 team.py "Build a user auth system with login and signup"
  python3 team.py --output ./src "Add a dark-mode toggle"
  python3 team.py                             # interactive mode
"""

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

try:
    from copilot import CopilotClient, PermissionHandler, StdioRuntimeConnection, UriRuntimeConnection, define_tool
except ImportError:
    CopilotClient = None
    PermissionHandler = None
    StdioRuntimeConnection = None
    UriRuntimeConnection = None
    define_tool = None

output_dir: Path = Path("./team_output").resolve()
feature_slug: str = "feature"
default_model: str = os.environ.get("TEAM_MODEL", "auto")
subagent_model: str = os.environ.get("TEAM_SUBAGENT_MODEL", default_model)

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
- alembic/         DB-migrationer. Nya/andrade modeller kraver en migration i alembic/versions/.

Rules for everyone:
- Read neighbouring files first (read_file / list_directory) and MATCH existing
  conventions and imports. Do not invent a parallel style.
- Write each file under its correct package path. Use relative paths from the repo root.
- NEVER overwrite root ARCHITECTURE.md, README.md or CLAUDE.md.
- Skip node_modules/.next/.venv — never read or write there.
"""

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


_IGNORE_DIRS = {"node_modules", ".next", ".git", ".venv", "venv", "__pycache__", "team_output"}


def _list_directory(path: str = ".") -> str:
    full = output_dir / path
    if not full.exists():
        return f"Error: {path} not found"
    entries = sorted(full.iterdir(), key=lambda item: (item.is_file(), item.name))
    lines = [
        ("  " if entry.is_file() else "D ") + entry.name
        for entry in entries
        if entry.name not in _IGNORE_DIRS
    ]
    return "\n".join(lines) if lines else "(empty)"


def _build_file_tools(role: str) -> list[Any]:
    async def write_file_handler(args: dict[str, Any], _invocation: Any) -> str:
        result = _write_file(args["path"], args["content"])
        print(f"  [{role}] wrote {args['path']}")
        return result

    async def read_file_handler(args: dict[str, Any], _invocation: Any) -> str:
        return _read_file(args["path"])

    async def list_directory_handler(args: dict[str, Any], _invocation: Any) -> str:
        return _list_directory(args.get("path", "."))

    return [
        define_tool(
            name="write_file",
            description=FILE_TOOLS[0]["description"],
            parameters=FILE_TOOLS[0]["input_schema"],
            handler=write_file_handler,
        ),
        define_tool(
            name="read_file",
            description=FILE_TOOLS[1]["description"],
            parameters=FILE_TOOLS[1]["input_schema"],
            handler=read_file_handler,
        ),
        define_tool(
            name="list_directory",
            description=FILE_TOOLS[2]["description"],
            parameters=FILE_TOOLS[2]["input_schema"],
            handler=list_directory_handler,
        ),
    ]


def _client_config() -> dict[str, Any]:
    if os.environ.get("COPILOT_CLI_URL"):
        return {
            "connection": UriRuntimeConnection(url=os.environ["COPILOT_CLI_URL"]),
            "working_directory": str(Path.cwd()),
        }

    return {
        "connection": StdioRuntimeConnection(path=_cli_path()),
        "working_directory": str(Path.cwd()),
    }


def _cli_path() -> str:
    return os.environ.get("COPILOT_CLI_PATH", "copilot")


def _require_sdk_dependencies() -> None:
    if (
        CopilotClient is None
        or PermissionHandler is None
        or StdioRuntimeConnection is None
        or UriRuntimeConnection is None
        or define_tool is None
    ):
        raise RuntimeError(
            "Missing Python dependency 'github-copilot-sdk'. Install it with: pip install -r requirements.txt"
        )


def _render_runtime_error(exc: Exception) -> str:
    message = str(exc)
    lines = [f"Copilot SDK run failed: {message}"]

    if "Access denied by policy settings" in message or "not authorized to use this Copilot feature" in message:
        lines.append("Copilot CLI access is blocked by policy or subscription settings.")
        lines.append("Check your Copilot settings: https://github.com/settings/copilot")
    elif "No such file or directory" in message or "not found" in message.lower():
        lines.append(f"Verify that COPILOT_CLI_PATH points to a valid Copilot CLI binary. Current value: {_cli_path()}")
    elif "Missing Python dependency 'github-copilot-sdk'" in message:
        lines.append("Install the SDK in the current Python environment before running team.py.")

    return "\n".join(lines)


def _event_type_name(event: Any) -> str:
    event_type = getattr(event, "type", "")
    return getattr(event_type, "value", event_type)


def _session_config(model: str, tools: list[Any], system_content: str) -> dict[str, Any]:
    return {
        "on_permission_request": PermissionHandler.approve_all,
        "model": model,
        "tools": tools,
        "system_message": {
            "mode": "append",
            "content": system_content,
        },
    }


async def _send_prompt_and_collect(session: Any, prompt: str) -> str:
    done = asyncio.Event()
    assistant_messages: list[str] = []
    session_errors: list[str] = []

    def handler(event: Any) -> None:
        event_type = _event_type_name(event)
        if event_type == "assistant.message":
            assistant_messages.append(event.data.content)
        elif event_type == "session.error":
            session_errors.append(getattr(event.data, "message", str(event.data)))
            done.set()
        elif event_type == "session.idle":
            done.set()

    unsubscribe = session.on(handler)
    try:
        await session.send(prompt)
        await done.wait()
    finally:
        unsubscribe()

    if session_errors:
        raise RuntimeError(session_errors[-1])

    return assistant_messages[-1] if assistant_messages else ""


AGENTS = {
    "architect": {
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
        "description": "Builds React components, custom hooks, and UI logic",
        "system": """\
You are the Frontend Developer. You build production-quality React/TypeScript UI.

Responsibilities:
- Write React functional components with full TypeScript types
- Create custom hooks for state and side effects
- Build accessible, responsive UIs with proper loading and error states
- Check ARCHITECTURE.md first if it exists — follow the plan

Conventions (this repo's real paths):
- Pages       -> apps/web/app/<route>/page.tsx  ("use client" + useRequireAuth for protected pages)
- Components  -> apps/web/components/<Feature>/...
- Hooks/utils -> apps/web/lib/use<Name>.ts
- API calls   -> use apps/web/lib/api.ts (add methods there, it attaches JWT automatically)
- UI          -> reuse apps/web/components/ui/primitives.tsx

Rules:
- Never skip error states or loading states
- Keep each file focused — no 500-line components
- Use TypeScript strictly — no `any`
- Match the existing client-side fetch pattern; do not invent a parallel data layer
""",
    },
    "backend": {
        "description": "Builds API routes, services, and data access layers",
        "system": """\
You are the Backend Developer. You build robust, secure FastAPI (Python 3.12) code.

Responsibilities:
- Add/extend FastAPI routers (APIRouter) in apps/api/app/routers/<resource>.py
- Define request/response DTOs in apps/api/app/dto.py (Pydantic v2; from_attributes for ORM serialization)
- Add SQLAlchemy 2.0 models to apps/api/app/models.py when persistence is needed,
  AND a matching Alembic migration in alembic/versions/ (follow the format in 0002_auth.py)
- Use the get_session dependency (apps/api/app/db.py) and auth deps
  (apps/api/app/deps.py: get_current_user, ensure_project_access) to protect and
  org-scope routes
- Register new routers in apps/api/app/main.py
- Check docs/plans/<feature-slug>.md first if it exists — follow the plan

Conventions (this repo's real paths):
- Routers -> apps/api/app/routers/<resource>.py
- DTOs    -> apps/api/app/dto.py
- Models  -> apps/api/app/models.py (+ alembic/versions/ migration)

Rules:
- Async SQLAlchemy throughout
- Validate all inputs with Pydantic — never trust user data
- Return consistent error shapes via HTTPException
- No secrets hardcoded — use os.environ
""",
    },
    "reviewer": {
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
- Explain why it's a problem
- For Critical/Major issues, show the fix
- Don't rewrite files — write docs/reviews/<feature-slug>.md only
- Skip pure style/naming preferences unless they cause confusion
""",
    },
}

DISPATCH_TOOL = {
    "name": "dispatch_agent",
    "description": (
        "Assign a task to a specialist sub-agent. "
        "Call it once per sub-task. All agents share the same output directory and can read each other's files."
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
                "description": "Clear, specific task for this agent.",
            },
            "context": {
                "type": "string",
                "description": "Optional context this agent needs.",
            },
        },
        "required": ["role", "task"],
    },
}

_AGENT_LIST = "\n".join(
    f"- {role}: {profile['description']}" for role, profile in AGENTS.items()
)

ORCHESTRATOR_SYSTEM = f"""\
You are the Engineering Lead. You receive feature requests and coordinate a team of specialists.

Your team:
{_AGENT_LIST}

How to work:
1. Think through what the feature needs before dispatching
2. Use the dispatch_agent tool to assign specific tasks
3. Typical flow for complex features:
   - architect first
   - then frontend + backend
   - reviewer last
4. For simple features, skip architect and dispatch directly to frontend/backend
5. When all work is done, summarize what was built

Rules:
- Be decisive — dispatch immediately, don't ask clarifying questions unless truly stuck
- Agents share the output directory; they can read each other's files
- Give each agent a specific, actionable task — not vague goals
"""


async def run_subagent(client: CopilotClient, role: str, task: str, context: str = "") -> str:
    profile = AGENTS.get(role)
    if not profile:
        return f"Error: unknown role '{role}'. Choose from: {', '.join(AGENTS)}"

    print(f"  [{role}] -> {task[:70]}{'...' if len(task) > 70 else ''}")

    system_content = (
        profile["system"]
        + "\n\n"
        + PROJECT_CONTEXT
        + f"\n\nFeature slug for doc paths: `{feature_slug}` "
        + f"(plan -> docs/plans/{feature_slug}.md, review -> docs/reviews/{feature_slug}.md)"
    )
    if context:
        system_content += f"\n\n## Context from orchestrator\n{context}"

    async with await client.create_session(
        **_session_config(subagent_model, _build_file_tools(role), system_content)
    ) as session:
        summary = await _send_prompt_and_collect(session, task)

    print(f"  [{role}] done")
    return summary or "(no summary)"


async def run_orchestrator(client: CopilotClient, goal: str) -> str:
    print(f"\nGoal: {goal}\n{'-' * 60}")

    orchestrator_system = (
        ORCHESTRATOR_SYSTEM
        + "\n\n"
        + PROJECT_CONTEXT
        + f"\n\nThis feature's slug is `{feature_slug}`. Pass it to agents so the "
        + f"architect writes docs/plans/{feature_slug}.md and the reviewer writes "
        + f"docs/reviews/{feature_slug}.md. Tell the reviewer exactly which files were created."
    )

    async def dispatch_handler(args: dict[str, Any], _invocation: Any) -> str:
        return await run_subagent(client, args["role"], args["task"], args.get("context", ""))

    dispatch_tool = define_tool(
        name=DISPATCH_TOOL["name"],
        description=DISPATCH_TOOL["description"],
        parameters=DISPATCH_TOOL["input_schema"],
        handler=dispatch_handler,
    )

    async with await client.create_session(
        **_session_config(default_model, [dispatch_tool], orchestrator_system)
    ) as session:
        summary = await _send_prompt_and_collect(session, goal)

    return summary or "(done)"


async def main_async(args: argparse.Namespace) -> None:
    _require_sdk_dependencies()

    global output_dir, feature_slug
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_slug = args.feature

    print(f"Output: {output_dir}")
    print(f"Feature: {feature_slug}")

    try:
        async with CopilotClient(**_client_config()) as client:
            if args.goal:
                summary = await run_orchestrator(client, args.goal)
                print(f"\n{'-' * 60}\n{summary}\n{'-' * 60}")
                return

            print("\nMulti-agent team ready. Type a feature goal (or 'quit').\n")
            while True:
                try:
                    goal = input("goal> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break

                if goal.lower() in {"quit", "exit", "q"}:
                    break
                if not goal:
                    continue

                summary = await run_orchestrator(client, goal)
                print(f"\n{'-' * 60}\n{summary}\n{'-' * 60}\n")
    except Exception as exc:
        raise RuntimeError(_render_runtime_error(exc)) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-agent engineering team — orchestrator + specialists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {role:<12} {profile['description']}" for role, profile in AGENTS.items()
        ),
    )
    parser.add_argument("goal", nargs="?", help="Feature to build (omit for interactive mode)")
    parser.add_argument(
        "--output",
        "-o",
        default="./team_output",
        help="Output directory (default: ./team_output; set to the repo root to write directly into the monorepo)",
    )
    parser.add_argument(
        "--feature",
        "-f",
        default="feature",
        help="Short feature slug controlling docs/plans/<slug>.md and docs/reviews/<slug>.md",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
