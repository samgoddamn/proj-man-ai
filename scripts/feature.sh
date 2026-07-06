#!/usr/bin/env bash
#
# Enkommando-flöde: agent-team bygger en feature och landar den i en pull request.
#
# Användning:
#   scripts/feature.sh <branch-namn> "<mål för featuren>"
#
# Exempel:
#   scripts/feature.sh dark-mode "Lägg till en dark-mode-toggle i frontenden"
#   scripts/feature.sh notes-api "CRUD-API för anteckningar kopplade till projekt"
#
# Vad det gör:
#   1. Kontrollerar att arbetsträdet är rent.
#   2. Skapar en färsk branch feat/<namn> från ett uppdaterat main.
#   3. Kör team.py (orkestrerare + specialistagenter) och skriver in i repo-roten.
#   4. Committar resultatet (med Co-Authored-By-trailer).
#   5. Pushar branchen och öppnar en pull request mot main (om gh finns).
#
# Kräver: GitHub Copilot CLI + github-copilot-sdk installerat. För PR-steget: gh CLI inloggad + git-remote.

set -euo pipefail

NAME="${1:-}"
GOAL="${2:-}"
if [[ -z "$NAME" || -z "$GOAL" ]]; then
  echo "Användning: scripts/feature.sh <branch-namn> \"<mål>\"" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

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

# 1. Rent arbetsträd krävs — annars blandas opågående ändringar in i committen.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "✗ Arbetsträdet är inte rent. Committa eller stasha först." >&2
  exit 1
fi

# slug: gemener, mellanslag → bindestreck
SLUG="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
BRANCH="feat/${SLUG}"

# 2. Färsk branch från main.
echo "▶  Skapar branch $BRANCH från main…"
git switch main
git pull --ff-only 2>/dev/null || echo "  (kunde inte pulla — fortsätter med lokalt main)"
git switch -c "$BRANCH"

# 3. Kör agent-teamet, skriv direkt in i monorepot.
echo "▶  Kör agent-teamet…"
python3 "$ROOT/team.py" --output "$ROOT" --feature "$SLUG" "$GOAL"

# Inget genererat? Avbryt utan tom commit.
if [[ -z "$(git status --porcelain)" ]]; then
  echo "✗ Teamet skapade inga ändringar. Avbryter (branch $BRANCH finns kvar lokalt)." >&2
  exit 1
fi

# 4. Committa.
echo "▶  Committar…"
git add -A
git commit -q -m "$(printf 'feat: %s\n\nGenererad av team.py.\nMål: %s\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>' "$NAME" "$GOAL")"

# 5. Push + PR.
if command -v gh >/dev/null 2>&1; then
  echo "▶  Pushar och öppnar PR…"
  git push -u origin "$BRANCH"
  gh pr create --fill --base main --body "$(printf 'Genererad av agent-teamet (team.py).\n\n**Mål:** %s\n\nPlan: `docs/plans/%s.md` · Granskning: `docs/reviews/%s.md`\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)' "$GOAL" "$SLUG" "$SLUG")"
else
  echo "⚠  gh CLI saknas — försöker pusha branchen ändå."
  git push -u origin "$BRANCH" \
    && echo "✓ Branch pushad. Öppna PR:n manuellt på GitHub." \
    || echo "✗ Push misslyckades (autentisering?). Branchen finns lokalt: $BRANCH"
fi

echo "✓ Klart. Branch: $BRANCH"
