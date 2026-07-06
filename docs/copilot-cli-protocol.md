# Local Copilot CLI JSON Protocol

This document defines the JSON contract expected by `llm_adapter.py` when
`team.py` is configured to use a local CLI via `COPILOT_CMD`.

Purpose
-------
- Give a local wrapper a stable output format.
- Allow `team.py` to keep its existing tool loop (`text` and `tool_use` blocks).
- Avoid coupling the orchestrator to a specific CLI vendor format.

How the adapter reads output
----------------------------
- If stdout is plain text, the adapter treats it as a single `text` block.
- If stdout contains JSON, the adapter tries to parse one of these shapes:

```json
{"content":[{"type":"text","text":"hello"}]}
```

or:

```json
[{"type":"text","text":"hello"}]
```

Supported block types
---------------------

Text block:

```json
{
  "type": "text",
  "text": "Done. I created the files."
}
```

Tool call block:

```json
{
  "type": "tool_use",
  "id": "tool-1",
  "name": "write_file",
  "input": {
    "path": "docs/example.md",
    "content": "# Example\n"
  }
}
```

Supported tools
---------------

Sub-agents receive these file tools:

```json
[
  {
    "name": "write_file",
    "input_schema": {
      "type": "object",
      "required": ["path", "content"]
    }
  },
  {
    "name": "read_file",
    "input_schema": {
      "type": "object",
      "required": ["path"]
    }
  },
  {
    "name": "list_directory",
    "input_schema": {
      "type": "object"
    }
  }
]
```

The orchestrator receives this dispatch tool:

```json
{
  "name": "dispatch_agent",
  "input": {
    "role": "backend",
    "task": "Add the route and DTO",
    "context": "Optional extra context"
  }
}
```

Expected control flow
---------------------
1. The adapter sends the prompt plus tool definitions to the CLI.
2. The CLI returns either text or JSON.
3. If at least one `tool_use` block is present, `team.py` executes the tool(s).
4. Tool results are appended back into the next prompt turn.

Minimal wrapper behavior
------------------------
- Read the full prompt from stdin.
- Decide whether to answer with text or one or more tool calls.
- Print only valid JSON on stdout when tool use is needed.
- Prefer a top-level array of blocks for simplicity.

Example wrapper outputs
-----------------------

Plain text response:

```json
[{"type":"text","text":"I reviewed the files and found no issues."}]
```

Single tool call:

```json
[
  {
    "type": "tool_use",
    "id": "tool-1",
    "name": "read_file",
    "input": {"path": "apps/api/app/dto.py"}
  }
]
```

Multiple tool calls in one turn:

```json
[
  {
    "type": "tool_use",
    "id": "tool-1",
    "name": "list_directory",
    "input": {"path": "apps/api/app/routers"}
  },
  {
    "type": "tool_use",
    "id": "tool-2",
    "name": "read_file",
    "input": {"path": "apps/api/app/main.py"}
  }
]
```

Text plus tool call:

```json
[
  {
    "type": "text",
    "text": "I need to inspect the existing router registration first."
  },
  {
    "type": "tool_use",
    "id": "tool-1",
    "name": "read_file",
    "input": {"path": "apps/api/app/main.py"}
  }
]
```

Failure handling
----------------
- If the CLI cannot produce valid JSON, plain text is still accepted.
- If JSON parsing fails, the adapter falls back to treating stdout as text.
- If a `tool_use` block has invalid `input`, the adapter normalizes it to `{}` and
  the tool execution layer will surface the real error.

Recommended wrapper interface
-----------------------------
- Environment variable:

```bash
export COPILOT_CMD="./scripts/copilot-wrapper.sh"
```

- Wrapper contract:
  - stdin: full prompt from the adapter
  - stdout: JSON matching this document
  - stderr: optional diagnostics only

Why this protocol exists
------------------------
- `gh copilot` and other local CLIs may change output formats or be blocked by org policy.
- This protocol keeps `team.py` isolated from those changes.
- A thin local wrapper can adapt any provider to this repo's existing multi-agent flow.