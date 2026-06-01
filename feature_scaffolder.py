#!/usr/bin/env python3
"""
Feature Scaffolder Agent
Accepts a feature description and generates the corresponding web app files
(components, routes, API endpoints) using Claude Opus 4.7.

Usage:
    python feature_scaffolder.py "A user profile page with avatar upload"
    python feature_scaffolder.py --output ./src "A shopping cart with checkout flow"
"""

import anthropic
import argparse
import json
import os
import sys
from pathlib import Path

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are an expert web app feature scaffolder. Given a feature description, you generate
all the files needed to implement it: React components, API route handlers, TypeScript types, and any
other relevant files.

Follow these conventions:
- Components go in components/<FeatureName>/
- API routes go in api/<feature-name>/route.ts (Next.js App Router style)
- Shared types go in types/<feature-name>.ts
- Use TypeScript throughout
- Components use functional style with hooks
- Keep each file focused and well-structured

Use the provided tools to create the files. Think through the full feature before writing any files —
decide what files are needed, what each one contains, and how they connect. Then write them all.

After writing all files, give a brief summary of what was created and how the pieces fit together."""


def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed."""
    full_path = Path(output_dir) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"Created {path} ({len(content)} bytes)"


def read_file(path: str) -> str:
    """Read an existing file."""
    full_path = Path(output_dir) / path
    if not full_path.exists():
        return f"Error: {path} does not exist"
    return full_path.read_text(encoding="utf-8")


def list_directory(path: str = ".") -> str:
    """List files and directories at a path."""
    full_path = Path(output_dir) / path
    if not full_path.exists():
        return f"Error: {path} does not exist"
    entries = sorted(full_path.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = []
    for entry in entries:
        prefix = "  " if entry.is_file() else "D "
        lines.append(f"{prefix}{entry.name}")
    return "\n".join(lines) if lines else "(empty)"


TOOLS = [
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Creates parent directories automatically. "
            "Use relative paths like 'components/UserProfile/index.tsx'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path, e.g. 'components/Auth/LoginForm.tsx'",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read an existing file. Useful for checking what was already written.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List the contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path. Defaults to '.' (output root).",
                    "default": ".",
                },
            },
            "required": [],
        },
    },
]

TOOL_HANDLERS = {
    "write_file": lambda inp: write_file(inp["path"], inp["content"]),
    "read_file": lambda inp: read_file(inp["path"]),
    "list_directory": lambda inp: list_directory(inp.get("path", ".")),
}


def execute_tool(name: str, tool_input: dict) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"Error: unknown tool '{name}'"
    try:
        return handler(tool_input)
    except Exception as e:
        return f"Error: {e}"


def scaffold(feature_description: str) -> str:
    """Run the agentic loop and return Claude's final summary."""
    print(f"\nScaffolding: {feature_description}")
    print(f"Output dir:  {output_dir}\n")

    messages = [{"role": "user", "content": feature_description}]
    files_written: list[str] = []

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            return final_text

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            # No tools called and not end_turn — treat remaining text as final
            return next((b.text for b in response.content if b.type == "text"), "")

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_block in tool_use_blocks:
            result = execute_tool(tool_block.name, tool_block.input)

            if tool_block.name == "write_file":
                files_written.append(tool_block.input["path"])
                print(f"  wrote  {tool_block.input['path']}")
            elif tool_block.name == "read_file":
                print(f"  read   {tool_block.input['path']}")
            elif tool_block.name == "list_directory":
                print(f"  ls     {tool_block.input.get('path', '.')}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                }
            )

        messages.append({"role": "user", "content": tool_results})


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold web app feature files from a description"
    )
    parser.add_argument("feature", help="Feature description, e.g. 'User profile page with avatar upload'")
    parser.add_argument(
        "--output",
        "-o",
        default="./scaffolded",
        help="Output directory (default: ./scaffolded)",
    )
    args = parser.parse_args()

    global output_dir
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = scaffold(args.feature)

    print("\n" + "─" * 60)
    print(summary)
    print("─" * 60)


output_dir: Path = Path("./scaffolded").resolve()

if __name__ == "__main__":
    main()
