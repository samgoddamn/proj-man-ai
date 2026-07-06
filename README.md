# AI Project Manager

En AI-driven projektledare för produktutveckling. Användaren skriver en
projektbeskrivning och får automatiskt en komplett projektstruktur: roadmap, epics,
user stories, tasks, sprintplanering, riskanalys och teknisk arkitektur — genererat
av en multi-agent-pipeline.

> Arkitektur och designbeslut i detalj: se **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Funktioner (MVP)

- **Projektskapande** med beskrivning, målgrupp, affärsmål, budget, tidsram.
- **Multi-agent-pipeline** (LangGraph): Discovery → Product Manager → Architect →
  Engineering → Scrum Master → QA → Health.
- **Roadmap, epics, user stories, tasks** genereras automatiskt.
- **Sprintplanering** utifrån teamstorlek och kapacitet.
- **Kanban-tavla** med drag & drop.
- **AI Project Health** — risker, beroenden, överbelastade sprintar.
- **Live-statusström** (SSE) som visar varje agents framsteg i realtid.
- **Auth** med JWT och organisations-scoping.
- **Provider-val:** Anthropic eller OpenAI.

## Teknikstack

| Lager | Teknik |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 |
| Databas | PostgreSQL (Alembic-migrationer) |
| Kö & realtid | Redis (jobbkö + pub/sub för SSE) |
| Agentorkestrering | LangGraph |
| AI | Anthropic API / OpenAI API |

## Projektstruktur

```
packages/agents/      Delad agent-kärna: scheman, LLM-abstraktion, noder, graph, prompts
apps/api/             FastAPI: modeller, routrar, auth, kö
workers/runner.py     Redis-konsument som kör pipelinen och persisterar resultatet
alembic/              Databasmigrationer
apps/web/             Next.js-frontend
docker-compose.yml    postgres + redis + migrate + api + worker (+ web via profil)
```

## Kom igång

### Förutsättningar
- Docker & Docker Compose
- En API-nyckel för Anthropic eller OpenAI

### 1. Konfigurera miljön
```bash
cp .env.example .env
# Redigera .env: sätt ANTHROPIC_API_KEY (eller OPENAI_API_KEY + LLM_PROVIDER=openai)
# och ett långt slumpmässigt JWT_SECRET.
```

### 2. Starta backend-stacken
```bash
docker compose up --build
```
Detta startar Postgres, Redis, kör migrationer (`migrate`-tjänsten) och startar sedan
`api` (http://localhost:8000) och `worker`.

- API-dokumentation (Swagger): http://localhost:8000/docs
- Hälsokoll: http://localhost:8000/health

### 3. Starta frontenden
Antingen via Compose-profilen:
```bash
docker compose --profile frontend up --build web
```
…eller lokalt under utveckling:
```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```
Frontenden körs på http://localhost:3000.

### 4. Använd appen
1. Gå till http://localhost:3000 → **Skapa ett konto**.
2. Skapa ett projekt och beskriv idén.
3. Följ agenterna arbeta live, och utforska roadmap, epics, sprintar och Kanban.

## Utveckling utanför Docker

**Backend** (kräver en körande Postgres + Redis):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=packages:apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_pm
export REDIS_URL=redis://localhost:6379
alembic upgrade head
uvicorn app.main:app --reload          # API
python workers/runner.py               # worker (separat terminal)
```

**Migrationer:**
```bash
alembic revision --autogenerate -m "beskrivning"   # skapa
alembic upgrade head                                 # applicera
```

## AI-driven feature-utveckling (team.py)

`team.py` är ett fristående multi-agent-team (orkestrerare + `architect`, `frontend`,
`backend`, `reviewer`) som bygger en hel feature från en målbeskrivning. Agenterna är
anpassade till det här monorepots stack (FastAPI i `apps/api`, Next.js i `apps/web`).

**Smidigaste vägen — ett kommando som bygger featuren OCH öppnar en PR:**
```bash
python3.12 -m pip install -r requirements.txt
export COPILOT_CLI_PATH="$HOME/Library/Application Support/Code/User/globalStorage/github.copilot-chat/copilotCli/copilot"
scripts/feature.sh <branch-namn> "<mål för featuren>"

# exempel
scripts/feature.sh dark-mode "Lägg till en dark-mode-toggle i frontenden"
```
Skriptet skapar `feat/<namn>` från `main`, kör agent-teamet (som skriver direkt in i
`apps/...`), committar, pushar och öppnar en pull request. Planen hamnar i
`docs/plans/<slug>.md` och en kodgranskning i `docs/reviews/<slug>.md`.

**Köra teamet utan git-flödet** (skriver till en sandlåda i stället):
```bash
python3.12 team.py --output ./team_output "Bygg X"
python3.12 team.py                              # interaktivt läge
```

**Köra `team.py` via GitHub Copilot SDK**

`team.py` använder nu GitHub Copilot Python SDK direkt. Du behöver:
- `github-copilot-sdk` installerat i din Python-miljö
- en lokal Copilot CLI-binär tillgänglig via `COPILOT_CLI_PATH` eller `PATH`

Snabbaste sättet att verifiera att SDK + CLI fungerar innan du kör hela teamet:

```bash
python3.12 scripts/copilot-sdk-smoke-test.py
```

Grundkonfiguration:

```bash
python3.12 -m pip install -r requirements.txt
export COPILOT_CLI_PATH="$HOME/Library/Application Support/Code/User/globalStorage/github.copilot-chat/copilotCli/copilot"
python3.12 team.py --output ./team_output "Bygg X"
```

Enklaste vägen lokalt är hjälpskriptet:

```bash
scripts/run-team-local.sh dark-mode "Lägg till en dark-mode-toggle i frontenden"
scripts/run-team-local.sh notes-api "Bygg ett CRUD-API för anteckningar" .
```

Det tredje argumentet är valfritt output-path. Använd `.` för att skriva direkt i
repot, annars används `./team_output`.

Begränsning:
- Om Copilot CLI blockeras av organisationspolicy eller saknar rättigheter kommer
  SDK-körningen inte kunna skapa features end-to-end.

> ⚠️ Agenterna har bara fil-verktyg — de kör inte bygg/tester. Granska PR:en och kör
> verifieringen (`npx tsc --noEmit && npm run build`, `py_compile`/tester) **innan**
> du mergar. Granskaragentens `docs/reviews/<slug>.md` är en hjälp, inte en garanti.

## Bidra (git-arbetsflöde)

Allt arbete sker på en feature-branch och landar via pull request — `main` ska alltid
vara stabil. Se **[CLAUDE.md](CLAUDE.md)** för det fullständiga arbetsflödet (det gäller
även AI-assisterade ändringar). Kort version:

```bash
git switch -c feat/min-andring     # ny branch från main
# ...gör ändringar, commit:a...
git push -u origin feat/min-andring
gh pr create --fill                # öppna pull request
```
