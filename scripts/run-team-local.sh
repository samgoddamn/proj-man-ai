#!/usr/bin/env bash
#
# Kor team.py via GitHub Copilot SDK.
#
# Användning:
#   scripts/run-team-local.sh <feature-slug> "<mål för featuren>" [output]
#
# Exempel:
#   scripts/run-team-local.sh dark-mode "Lägg till en dark-mode-toggle i frontenden"
#   scripts/run-team-local.sh notes-api "CRUD-API för anteckningar" .
#
# Vad det gör:
#   1. Letar upp en lokal Copilot CLI-binär.
#   2. Verifierar att Python-SDK:n finns installerad.
#   3. Kör team.py med angiven feature-slug och mål.
#
# Kör `scripts/copilot-sdk-smoke-test.py` först om du vill verifiera SDK + CLI
# utan att starta hela multi-agent-flödet.
#
# Standard-output är ./team_output. Skicka '.' som tredje argument för att skriva
# direkt i repot.

set -euo pipefail

SLUG="${1:-}"
GOAL="${2:-}"
OUTPUT_ARG="${3:-}"

if [[ -z "$SLUG" || -z "$GOAL" ]]; then
  echo "Användning: scripts/run-team-local.sh <feature-slug> \"<mål>\" [output]" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUTPUT="${OUTPUT_ARG:-$ROOT/team_output}"
LOG_FILE="$(mktemp)"
trap 'rm -f "$LOG_FILE"' EXIT

DEFAULT_CLI_PATH="$(command -v copilot || true)"
if [[ -z "$DEFAULT_CLI_PATH" ]]; then
  VSCODE_CLI_PATH="$HOME/Library/Application Support/Code/User/globalStorage/github.copilot-chat/copilotCli/copilot"
  if [[ -x "$VSCODE_CLI_PATH" ]]; then
    DEFAULT_CLI_PATH="$VSCODE_CLI_PATH"
  fi
fi

export COPILOT_CLI_PATH="${COPILOT_CLI_PATH:-$DEFAULT_CLI_PATH}"

if [[ -z "$COPILOT_CLI_PATH" || ! -x "$COPILOT_CLI_PATH" ]]; then
  echo "✗ Hittar ingen Copilot CLI-binär. Sätt COPILOT_CLI_PATH manuellt." >&2
  exit 1
fi

if ! python3 -c 'import copilot' >/dev/null 2>&1; then
  echo "✗ Python-paketet github-copilot-sdk saknas i nuvarande miljö." >&2
  echo "  Installera med: pip install -r requirements.txt" >&2
  exit 1
fi

echo "▶  Kör team.py via GitHub Copilot SDK…"
echo "   Feature: $SLUG"
echo "   Output:  $OUTPUT"
echo "   CLI:     $COPILOT_CLI_PATH"

python3 "$ROOT/team.py" --output "$OUTPUT" --feature "$SLUG" "$GOAL" | tee "$LOG_FILE"

if grep -q "Access denied by policy settings" "$LOG_FILE"; then
  echo "✗ Copilot CLI blockerades av policy. Ingen feature genererades." >&2
  echo "  Tips: kör scripts/copilot-sdk-smoke-test.py eller verifiera Copilot-behörigheten i GitHub Copilot-inställningarna." >&2
  exit 1
fi
