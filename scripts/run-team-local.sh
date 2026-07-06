#!/usr/bin/env bash
#
# Kör team.py via den lokala Copilot-wrappern.
#
# Användning:
#   scripts/run-team-local.sh <feature-slug> "<mål för featuren>" [output]
#
# Exempel:
#   scripts/run-team-local.sh dark-mode "Lägg till en dark-mode-toggle i frontenden"
#   scripts/run-team-local.sh notes-api "CRUD-API för anteckningar" .
#
# Vad det gör:
#   1. Pekar team.py mot scripts/copilot-wrapper.py.
#   2. Sätter rimliga standardvärden för lokal Copilot CLI-körning.
#   3. Kör team.py med angiven feature-slug och mål.
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

export COPILOT_CMD="${COPILOT_CMD:-$ROOT/scripts/copilot-wrapper.py}"
export COPILOT_WRAPPER_BACKEND="${COPILOT_WRAPPER_BACKEND:-gh}"
export COPILOT_WRAPPER_ARGS="${COPILOT_WRAPPER_ARGS:-copilot -p}"
export COPILOT_WRAPPER_PROMPT_MODE="${COPILOT_WRAPPER_PROMPT_MODE:-arg}"

echo "▶  Kör team.py via lokal wrapper…"
echo "   Feature: $SLUG"
echo "   Output:  $OUTPUT"
echo "   Cmd:     $COPILOT_CMD"
echo "   Backend: $COPILOT_WRAPPER_BACKEND $COPILOT_WRAPPER_ARGS"

if [[ -n "${COPILOT_WRAPPER_MOCK_RESPONSE:-}" ]]; then
  echo "   Mock:    aktiv (COPILOT_WRAPPER_MOCK_RESPONSE satt)"
fi

python3 "$ROOT/team.py" --output "$OUTPUT" --feature "$SLUG" "$GOAL" | tee "$LOG_FILE"

if grep -q "Access denied by policy settings" "$LOG_FILE"; then
  echo "✗ Copilot CLI blockerades av policy. Ingen feature genererades." >&2
  echo "  Tips: verifiera Copilot-behörigheten eller testa med COPILOT_WRAPPER_MOCK_RESPONSE först." >&2
  exit 1
fi
