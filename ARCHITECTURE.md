# Teknisk plan: AI Project Manager SaaS

En webbaserad SaaS-plattform som fungerar som en AI-driven projektledare. Användaren
skriver en projektbeskrivning och får automatiskt genererat: roadmap, epics, user
stories, tasks, prioriteringar, sprintplanering, riskanalys och teknisk arkitektur.

---

## 1. Övergripande arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 14 App Router · TS · Tailwind · shadcn)   │
│  - Projektwizard   - Roadmap/Epics-vy   - Kanban   - Health   │
└───────────────┬───────────────────────────────────────────────┘
                │  REST + SSE (streaming agent-status)
┌───────────────▼───────────────────────────────────────────────┐
│  API  (FastAPI · Python 3.12 · Pydantic v2)                    │
│  - Auth/CRUD   - /generate triggers   - SSE-status-stream      │
└───────┬───────────────────────────────────┬───────────────────┘
        │ enqueue job                        │ read/write
┌───────▼──────────┐              ┌──────────▼──────────┐
│  Redis           │              │  PostgreSQL          │
│  - Job queue     │              │  - Domändata         │
│  - Pub/Sub (SSE) │              │  - Agent-run-logg    │
│  - Rate limiting │              │  - pgvector (V2)     │
└───────┬──────────┘              └─────────────────────┘
        │ dequeue
┌───────▼───────────────────────────────────────────────────────┐
│  Worker  (Python · LangGraph)                                  │
│  Discovery → ProductManager → Architect → Engineering          │
│             → ScrumMaster → QA   (state-maskin, se §4)          │
└────────────────────────────────────────────────────────────────┘
```

**Bärande designbeslut:** AI-generering körs **aldrig** i request-tråden. En klient
POST:ar ett jobb, får tillbaka ett `run_id`, och prenumererar på status via SSE. En
full pipeline (6 agenter, många LLM-anrop) tar 30 s–flera minuter och får inte blockera
HTTP-timeouts.

---

## 2. Mappstruktur (monorepo)

```
ai-pm/
├── apps/
│   ├── web/                      # Next.js
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   ├── projects/[id]/
│   │   │   │   ├── roadmap/  epics/  kanban/  health/
│   │   │   └── projects/new/
│   │   ├── components/ui/        # shadcn
│   │   ├── components/kanban/
│   │   └── lib/api.ts            # typad fetch-klient
│   └── api/                      # FastAPI
│       ├── app/
│       │   ├── main.py
│       │   ├── routers/          # projects, generation, board, health, auth
│       │   ├── models/           # SQLAlchemy
│       │   ├── schemas/          # Pydantic DTOs
│       │   ├── services/         # affärslogik
│       │   ├── queue/            # Redis enqueue + SSE pub/sub
│       │   └── db.py
│       └── alembic/
├── packages/
│   └── agents/                   # delad agent-kärna (importeras av worker)
│       ├── graph.py              # LangGraph-definition
│       ├── state.py              # delat AgentState (Pydantic)
│       ├── nodes/                # en fil per agent
│       ├── prompts/              # versionerade systemprompts
│       └── llm.py                # provider-abstraktion (OpenAI/Anthropic)
├── workers/
│   └── runner.py                 # konsumerar Redis-kö, kör graph
├── docker-compose.yml            # postgres + redis + api + worker + web
└── .env.example
```

Worker och API delar samma SQLAlchemy-modeller och `packages/agents`. Håll
agent-logiken provideroberoende bakom `llm.py` — plattformen ska stödja valbar
OpenAI/Anthropic.

---

## 3. Datamodell

PostgreSQL via SQLAlchemy 2.0 + Alembic.

```
users          id, email, hashed_password, name, created_at
organizations  id, name, owner_id
memberships    user_id, org_id, role            # owner|admin|member

projects       id, org_id, name, description,
               target_audience, business_goals,
               budget?, timeframe?, status, created_at
                 status: draft | generating | ready | failed

roadmaps       id, project_id, phase(int), title, summary, order
epics          id, project_id, roadmap_id?, title, description,
               priority(int), business_value, order
user_stories   id, epic_id, role, want, so_that, acceptance_criteria(jsonb), order
tasks          id, story_id, title, description, type(backend|frontend|test|infra),
               status, estimate(points), sprint_id?, board_order, created_at
                 status: backlog | todo | in_progress | review | done

sprints        id, project_id, name, goal, start_date, end_date,
               capacity_points, order
architecture   id, project_id, stack(jsonb), data_model(jsonb),
               api_design(jsonb), rationale(text)   # Architect-output
risks          id, project_id, title, description, severity,
               affected_epics(jsonb), recommendation, source

agent_runs     id, project_id, status, current_agent, started_at,
               finished_at, error?
agent_steps    id, run_id, agent_name, status, input_tokens,
               output_tokens, latency_ms, raw_output(jsonb), created_at
```

**Varför de extra tabellerna (utöver beskrivningens bas):**
- `agent_runs` / `agent_steps` — utan dem är pipelinen en svart låda. Behövs för
  felsökning, kostnadsspårning och för att driva live-statusen i UI.
- `board_order` (float) på tasks — gör drag & drop-omsortering till en enda
  fältuppdatering utan att numrera om hela kolumnen.
- `architecture` och `risks` som egna tabeller — direkt output från Architect-
  respektive Health-analysen; måste persisteras, inte bara visas.

---

## 4. Agent-orkestrering (LangGraph)

**Rekommendation: LangGraph framför PydanticAI** för MVP. Pipelinen är en sekventiell
graf med delat tillstånd, villkorad förgrening (failure/retry) och behov av att strömma
per-nod-status — LangGraphs sweet spot. (PydanticAI är bra för enskilda strukturerade
agenter, men då bygger man orkestreringen själv.)

**Delad state:**
```python
class AgentState(BaseModel):
    project_id: UUID
    run_id: UUID
    brief: ProjectBrief                 # input
    discovery: DiscoveryOutput | None
    roadmap: list[RoadmapPhase] | None
    epics: list[EpicDraft] | None
    architecture: ArchitectureDraft | None
    stories: list[StoryDraft] | None
    tasks: list[TaskDraft] | None
    sprints: list[SprintDraft] | None
    risks: list[RiskDraft] | None
    errors: list[str]
```

**Graf-flöde (notera ordningen — skiljer sig från beskrivningens numrering):**
```
       discovery
           │
     product_manager        (roadmap + epics)
           │
       architect            (parallell-kandidat)
           │
       engineering          (stories + tasks, fan-out per epic)
           │
       scrum_master         (sprintar — behöver tasks+estimat)
           │
        qa_agent            (testplan per story)
           │
       health_check         (risker — behöver hela bilden)
           │
          END
```

Viktig avvikelse från dokumentets agentlista: **Scrum Master måste köra efter
Engineering**, inte före — sprintplanering kräver task-estimat för kapacitetsberäkning.
**Health sist** — risker kräver hela bilden. Dokumentets numrering är presentations-
ordning, inte exekveringsordning.

**Per nod:**
- Varje nod = ett LLM-anrop med **structured output** (Pydantic-schema via
  `response_format` / tool-call). Aldrig fri text som parsas med regex.
- Varje nod skriver en `agent_steps`-rad och publicerar `run:{run_id}` på Redis pub/sub
  → SSE till frontend.
- `engineering`-noden gör fan-out: en delgenerering per epic (parallellt med
  `asyncio.gather`, begränsat med semafor) för att hålla nere latens och kontextstorlek.

**Felhantering:** villkorad kant efter varje nod — vid schema-valideringsfel, retry
(max 2) med felet inmatat i prompten; därefter markera `agent_runs.status = failed` och
behåll allt som hann genereras (partial success).

---

## 5. API-design

```
POST   /auth/register · /auth/login
GET    /projects                      # lista
POST   /projects                      # skapa (draft)
GET    /projects/{id}                 # full hierarki
POST   /projects/{id}/generate        # enqueue pipeline → {run_id}
GET    /projects/{id}/runs/{run_id}/stream   # SSE: agent-status live
GET    /projects/{id}/roadmap · /epics · /sprints · /architecture · /risks

GET    /projects/{id}/board           # tasks grupperade per status
PATCH  /tasks/{id}                    # status / board_order / sprint_id
POST   /projects/{id}/health/refresh  # kör om health_check-agenten

POST   /projects/{id}/sprints/plan    # kör om Scrum Master (team_size, sprint_length)
```

SSE-payloads: `{"agent":"product_manager","status":"running|done","progress":0.4}`.

---

## 6. Frontend-flöde

1. **`/projects/new`** — wizard med fälten (namn, beskrivning, målgrupp, affärsmål,
   budget?, tidsram?). Submit → skapar draft + triggar `/generate`.
2. **Genererings-vy** — prenumererar på SSE, visar de 6 agenterna som en checklista som
   fylls i live. Detta är "wow"-momentet; värt egen polish.
3. **Projektvy** — flikar: Roadmap (faser), Epics→Stories→Tasks (träd), Arkitektur,
   Sprintar.
4. **Kanban** — `@dnd-kit` för drag & drop; PATCH vid släpp. Knapp "AI: prioritera om"
   → triggar omsortering.
5. **Health** — risk-kort med severity och rekommendation; "uppdatera analys".

---

## 7. Bygg-ordning för MVP (vertikalt, inte lager-för-lager)

| Steg | Leverans | Varför |
|---|---|---|
| 0 | docker-compose: pg + redis + tom api + web | Infra på plats |
| 1 | Auth + Projects CRUD (ingen AI) | Skelett som funkar end-to-end |
| 2 | `llm.py` + **Discovery-agenten ensam**, synkront | Bevisa LLM-integration + structured output billigt |
| 3 | Redis-kö + worker + SSE-status | Den asynkrona ryggraden |
| 4 | Full LangGraph-pipeline (alla 6 agenter) | Kärnvärdet |
| 5 | Läsvyer: roadmap/epics/stories/tasks | Visa resultatet |
| 6 | Kanban + drag & drop + PATCH | Interaktivitet |
| 7 | Health-analys + AI-omprioritering | "Agent, inte chatbot"-känslan |

Stoppa **inte** efter steg 1 i flera veckor — steg 2 (en enda agent end-to-end)
avriskerar hela produkten och bör göras tidigt.

---

## 8. Teknikstack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, @dnd-kit
- **Backend:** FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0, Alembic
- **Databas:** PostgreSQL (pgvector i V2)
- **Köhantering & realtid:** Redis (job queue + pub/sub för SSE)
- **Agentorkestrering:** LangGraph
- **AI:** OpenAI API och/eller Anthropic API bakom egen provider-abstraktion

---

## 9. Risker & rekommendationer

- **Latens & kostnad:** 6 agenter × flera anrop kan bli dyrt och långsamt per projekt.
  Mitigering: structured output, fan-out-parallellisering, och prompt-caching
  (systemprompts + projektbrief cachas mellan agentstegen — stor besparing eftersom
  briefen återanvänds i varje nod).
- **JSON-tillförlitlighet:** lita aldrig på fri text. Använd providers
  structured-output-läge + Pydantic-validering + retry. Vanligaste felkällan i
  agent-pipelines.
- **Idempotens:** `/generate` på ett redan genererat projekt — bestäm tidigt:
  versionera runs, eller blockera om `status != draft`. Annars dubbletter.
- **Provider-abstraktion:** håll OpenAI/Anthropic bakom ett interface från dag ett (du
  vill testa Opus vs GPT på samma pipeline). Med Anthropic: utnyttja prompt caching och
  structured tool-use.
- **Agentordning:** Scrum Master efter Engineering, Health sist (se §4).
- **Scope-fälla:** V2-listan (GitHub/Jira/Slack/burndown) är frestande men distraherar.
  MVP = generera + visa + Kanban + health. Inget mer.

---

## 10. V2 (framtida funktioner)

GitHub-integration · Jira-import · Slack-integration · automatisk PR-granskning · AI
Daily Standup · burndown-prognoser · kostnadsprognoser · multi-projektportfölj · team
performance analytics.
