#!/usr/bin/env python3
"""Minimal connectivity test for the GitHub Copilot Python SDK.

This verifies three things:
1. The Python SDK import works.
2. The configured Copilot CLI binary can be started.
3. A simple session can answer one prompt.
"""

from __future__ import annotations

import asyncio
import os
import sys

try:
    from copilot import CopilotClient, PermissionHandler, StdioRuntimeConnection, UriRuntimeConnection
except ImportError as exc:
    print("Missing dependency: github-copilot-sdk", file=sys.stderr)
    print("Install it with: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(1) from exc


def _client_config() -> dict[str, object]:
    if os.environ.get("COPILOT_CLI_URL"):
        return {"connection": UriRuntimeConnection(url=os.environ["COPILOT_CLI_URL"])}

    return {"connection": StdioRuntimeConnection(path=os.environ.get("COPILOT_CLI_PATH", "copilot"))}


async def main() -> int:
    cli_path = os.environ.get("COPILOT_CLI_PATH", "copilot")
    print(f"Using Copilot CLI: {cli_path}")

    try:
        async with CopilotClient(**_client_config()) as client:
            response = await client.ping("health check")
            print(f"Ping ok: {response.timestamp} ({response.message})")

            async with await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=os.environ.get("TEAM_MODEL", "gpt-5"),
            ) as session:
                event = await session.send_and_wait("Reply with exactly: sdk-ok", timeout=60.0)

            if event and event.type == "assistant.message":
                print(f"Assistant reply: {event.data.content}")
                return 0

            print("No assistant.message event received", file=sys.stderr)
            return 1
    except Exception as exc:
        message = str(exc)
        print(f"Smoke test failed: {message}", file=sys.stderr)
        if "Access denied by policy settings" in message or "not authorized to use this Copilot feature" in message:
            print("Copilot CLI access is blocked by policy or subscription settings.", file=sys.stderr)
            print("Check https://github.com/settings/copilot", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))