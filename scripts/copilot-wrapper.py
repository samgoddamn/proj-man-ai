#!/usr/bin/env python3
"""Normalize a local CLI's output into the repo's JSON protocol.

Usage:
  export COPILOT_CMD="./scripts/copilot-wrapper.py"
  export COPILOT_WRAPPER_BACKEND="gh"
  export COPILOT_WRAPPER_ARGS="copilot -p"
  python3 team.py "Add login"

Environment variables:
  COPILOT_WRAPPER_BACKEND
    Executable to run. Default: `gh`

  COPILOT_WRAPPER_ARGS
    Space-separated args for the backend executable. Default: `copilot -p`

  COPILOT_WRAPPER_PROMPT_MODE
    How the backend receives the prompt: `arg` or `stdin`. Default: `arg`
    - `arg`: append the full prompt as the final argument
    - `stdin`: send the full prompt to stdin

  COPILOT_WRAPPER_MOCK_RESPONSE
    If set, skip the backend call and use this value as stdout. Useful for tests.

The wrapper prints a top-level JSON array of protocol blocks to stdout.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any


def _debug(message: str) -> None:
    if os.environ.get("COPILOT_WRAPPER_DEBUG") == "1":
        print(message, file=sys.stderr)


def _extract_json_payload(stdout: str) -> Any | None:
    stdout = stdout.strip()
    if not stdout:
        return None

    candidates = [stdout]

    if "```json" in stdout:
        start = stdout.find("```json") + len("```json")
        end = stdout.find("```", start)
        if end != -1:
            candidates.append(stdout[start:end].strip())

    first_brace = stdout.find("{")
    first_bracket = stdout.find("[")
    starts = [idx for idx in (first_brace, first_bracket) if idx != -1]
    if starts:
        candidates.append(stdout[min(starts):].strip())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return None


def _normalize_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        payload = payload["content"]

    if isinstance(payload, list):
        normalized: list[dict[str, Any]] = []
        for index, block in enumerate(payload):
            if not isinstance(block, dict):
                normalized.append({"type": "text", "text": str(block)})
                continue

            if block.get("type") == "tool_use":
                normalized.append(
                    {
                        "type": "tool_use",
                        "id": str(block.get("id") or f"tool-{index}"),
                        "name": str(block.get("name", "")),
                        "input": block.get("input", {}) if isinstance(block.get("input", {}), dict) else {},
                    }
                )
            else:
                normalized.append({"type": "text", "text": str(block.get("text", ""))})
        return normalized

    return [{"type": "text", "text": str(payload)}]


def _run_backend(prompt: str) -> str:
    mock_response = os.environ.get("COPILOT_WRAPPER_MOCK_RESPONSE")
    if mock_response is not None:
        _debug("Using COPILOT_WRAPPER_MOCK_RESPONSE")
        return mock_response

    backend = os.environ.get("COPILOT_WRAPPER_BACKEND", "gh")
    args = shlex.split(os.environ.get("COPILOT_WRAPPER_ARGS", "copilot -p"))
    prompt_mode = os.environ.get("COPILOT_WRAPPER_PROMPT_MODE", "arg")

    command = [backend, *args]
    stdin_data: str | None = None
    if prompt_mode == "stdin":
        stdin_data = prompt
    else:
        command.append(prompt)

    _debug(f"Running backend: {command}")

    proc = subprocess.run(
        command,
        input=stdin_data,
        text=True,
        capture_output=True,
        timeout=120,
    )

    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()

    if proc.returncode != 0:
        error_output = (stderr or stdout or "").strip()
        raise RuntimeError(f"Backend command failed with exit code {proc.returncode}: {error_output}")

    # Some local CLIs report policy or auth failures on stderr while still exiting 0.
    if not stdout and stderr:
        return stderr

    return stdout


def main() -> int:
    prompt = sys.stdin.read()
    if not prompt:
        print(json.dumps([{"type": "text", "text": "No prompt provided on stdin."}]))
        return 0

    try:
        stdout = _run_backend(prompt)
    except Exception as exc:
        print(json.dumps([{"type": "text", "text": f"Wrapper error: {exc}"}]))
        return 0

    payload = _extract_json_payload(stdout)
    if payload is None:
        normalized = [{"type": "text", "text": stdout}]
    else:
        normalized = _normalize_payload(payload)

    print(json.dumps(normalized, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())