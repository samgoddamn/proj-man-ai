"""Adapter for a local Copilot/LLM CLI.

The command is configured via `COPILOT_CMD`. The adapter supports two output modes:

1. Plain text: stdout becomes a single `text` block.
2. Structured JSON: stdout may contain either a JSON object with a `content` list,
   or a top-level JSON array of content blocks.

Supported block shapes:
  {"type": "text", "text": "..."}
  {"type": "tool_use", "id": "...", "name": "write_file", "input": {...}}

If any `tool_use` blocks are present, `stop_reason` is set so `team.py` continues
the tool loop instead of ending immediately.

Protocol reference: docs/copilot-cli-protocol.md
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class TextBlock:
    type: str
    text: str


@dataclass
class ToolUseBlock:
    type: str
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class Response:
    stop_reason: str
    content: List[Any]


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=True))
            elif hasattr(item, "type") and getattr(item, "type") == "text":
                parts.append(getattr(item, "text", ""))
            elif hasattr(item, "type") and getattr(item, "type") == "tool_use":
                parts.append(
                    json.dumps(
                        {
                            "type": "tool_use",
                            "id": getattr(item, "id", ""),
                            "name": getattr(item, "name", ""),
                            "input": getattr(item, "input", {}),
                        },
                        ensure_ascii=True,
                    )
                )
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _build_prompt(system: str, messages: List[Dict[str, str]]) -> str:
    parts = ["SYSTEM:", system.strip(), ""]
    for m in messages:
        role = m.get("role", "user")
        content = _stringify_content(m.get("content", ""))
        parts.append(f"{role.upper()}: {content}")
    return "\n".join(parts)


def _build_tool_instructions(tools: List[Dict[str, Any]] | None) -> str:
    if not tools:
        return ""

    tool_lines = []
    for tool in tools:
        tool_lines.append(
            json.dumps(
                {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "input_schema": tool.get("input_schema"),
                },
                ensure_ascii=True,
            )
        )

    return "\n".join(
        [
            "",
            "TOOLS:",
            *tool_lines,
            "",
            "RESPONSE FORMAT:",
            "Return only valid JSON.",
            "If you want to call one or more tools, return a JSON array of blocks like:",
            '[{"type":"tool_use","id":"tool-1","name":"<tool name>","input":{...}}]',
            "If you want to answer normally, return either:",
            '{"content":[{"type":"text","text":"..."}]}',
            "or:",
            '[{"type":"text","text":"..."}]',
            "Do not wrap JSON in explanations unless unavoidable.",
        ]
    )


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
        start = min(starts)
        candidates.append(stdout[start:].strip())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return None


def _build_response_from_payload(payload: Any) -> Response:
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        raw_blocks = payload["content"]
        stop_reason = payload.get("stop_reason")
    elif isinstance(payload, list):
        raw_blocks = payload
        stop_reason = None
    else:
        return Response(stop_reason="end_turn", content=[TextBlock(type="text", text=str(payload))])

    blocks: List[Any] = []
    has_tool_use = False
    for index, block in enumerate(raw_blocks):
        if not isinstance(block, dict):
            blocks.append(TextBlock(type="text", text=str(block)))
            continue

        block_type = block.get("type")
        if block_type == "tool_use":
            has_tool_use = True
            blocks.append(
                ToolUseBlock(
                    type="tool_use",
                    id=str(block.get("id") or f"tool-{index}"),
                    name=str(block.get("name", "")),
                    input=block.get("input", {}) if isinstance(block.get("input", {}), dict) else {},
                )
            )
        else:
            blocks.append(TextBlock(type="text", text=str(block.get("text", ""))))

    if stop_reason is None:
        stop_reason = "tool_use" if has_tool_use else "end_turn"

    return Response(stop_reason=stop_reason, content=blocks)


def send_request(system: str, messages: List[Dict[str, str]], tools=None, max_tokens: int = 16000) -> Response:
    """Send a prompt to the local Copilot CLI.

        The environment variable `COPILOT_CMD` controls the command to run. It should
        accept stdin and print the assistant reply on stdout. Example values:
            - "copilot"
            - "gh copilot -p"
            - "./local-copilot.sh"

    If the command fails, the error text is returned as the assistant reply.
    """
    cmd = os.environ.get("COPILOT_CMD", "copilot")
    prompt = _build_prompt(system, messages) + _build_tool_instructions(tools)

    try:
        proc = subprocess.run(cmd, input=prompt, text=True, shell=True, capture_output=True, timeout=120)
        stdout = proc.stdout.strip()
        if not stdout and proc.stderr:
            stdout = proc.stderr.strip()
    except Exception as exc:
        stdout = f"Error invoking COPILOT_CMD={cmd}: {exc}"

    payload = _extract_json_payload(stdout)
    if payload is not None:
        return _build_response_from_payload(payload)

    return Response(stop_reason="end_turn", content=[TextBlock(type="text", text=stdout)])


__all__ = ["send_request", "Response", "TextBlock", "ToolUseBlock"]
