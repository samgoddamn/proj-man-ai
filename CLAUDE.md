# CLAUDE.md

Projektkonventioner för AI Project Manager. Läs detta innan du gör ändringar.

## Översikt
- Arkitektur & designbeslut: `ARCHITECTURE.md`
- Körinstruktioner: `README.md`
- Backend: `apps/api/` (FastAPI), agent-kärna: `packages/agents/` (LangGraph),
  worker: `workers/runner.py`, frontend: `apps/web/` (Next.js).

## Git-arbetsflöde (OBLIGATORISKT)

**Committa aldrig direkt till `main`.** Varje ändring ska ske på en egen branch och
landa via en pull request. Detta gäller alla ändringar, inklusive AI-assisterade.

För varje ny uppgift som innebär ändringar i koden:

1. **Skapa en ny branch från ett uppdaterat `main`** innan du redigerar något:
   ```bash
   git switch main && git pull --ff-only
   git switch -c <typ>/<kort-beskrivning>
   ```
   Branch-namn använder prefix: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`.
   Exempel: `feat/openai-streaming`, `fix/sprint-capacity-rounding`.

2. **Gör ändringarna och committa** med tydliga meddelanden:
   ```bash
   git add -A
   git commit -m "<imperativ sammanfattning>"
   ```
   Avsluta varje commit-meddelande med:
   ```
   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```

3. **Pusha branchen och öppna en pull request:**
   ```bash
   git push -u origin <branch>
   gh pr create --fill --base main
   ```
   Avsluta PR-beskrivningen med:
   ```
   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

4. **Slå inte ihop PR:en själv** utan att användaren ber om det. Lämna den öppen för
   granskning.

### Förutsättningar för PR-steget
Pull requests kräver ett git-remote (t.ex. GitHub) och `gh` CLI inloggad
(`gh auth login`). Om inget remote är konfigurerat: skapa branchen och committa ändå,
och tala om för användaren att remote + `gh` behöver sättas upp för att PR ska kunna
öppnas.

## Verifiering före PR
- Backend (Python): `python -m py_compile` på ändrade filer; kör relevanta tester.
- Frontend: `cd apps/web && npx tsc --noEmit && npm run build`.
- Migrationer: verifiera DDL med `alembic upgrade head --sql` innan du litar på dem.
