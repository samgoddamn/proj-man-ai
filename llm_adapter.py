"""Simple adapter to call a local Copilot/LLM CLI.

Configure the command via the `COPILOT_CMD` env var (default: `copilot`).
The adapter sends the concatenated system+messages as plain text on stdin to the
configured command and returns the stdout as the assistant reply.

This is intentionally minimal: it does NOT emulate tool_use blocks. It provides a
compatible minimal response object for `team.py` to consume so you can run the
orchestrator against a local Copilot CLI.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Response:
    stop_reason: str
    content: List[Dict[str, Any]]


def _build_prompt(system: str, messages: List[Dict[str, str]]) -> str:
    parts = ["SYSTEM:", system.strip(), ""]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    return "\n".join(parts)


def send_request(system: str, messages: List[Dict[str, str]], tools=None, max_tokens: int = 16000) -> Response:
    """Send a prompt to the local Copilot CLI.

    The environment variable `COPILOT_CMD` controls the command to run. It should
    accept stdin and print the assistant reply on stdout. Example values:
      - "copilot"
      - "gh copilot chat"
      - "./local-copilot.sh"

    If the command fails, the error text is returned as the assistant reply.
    """
    cmd = os.environ.get("COPILOT_CMD", "copilot")
    prompt = _build_prompt(system, messages)

    try:
        proc = subprocess.run(cmd, input=prompt, text=True, shell=True, capture_output=True, timeout=120)
        stdout = proc.stdout.strip()
        if not stdout and proc.stderr:
            stdout = proc.stderr.strip()
    except Exception as exc:
        stdout = f"Error invoking COPILOT_CMD={cmd}: {exc}"

    # Minimal response object expected by team.py
    blocks = [{"type": "text", "text": stdout}]
    return Response(stop_reason="end_turn", content=blocks)


__all__ = ["send_request", "Response"]
