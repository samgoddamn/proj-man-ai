# Review instructions

Granskningsinstruktioner för AI Project Manager — ett monorepo med FastAPI-backend
(`apps/api`), Next.js-frontend (`apps/web`), LangGraph-agentpipeline
(`packages/agents`), worker (`workers/`) och Alembic-migrationer (`alembic/`).

Dessa regler har högsta prioritet. Var konkret: citera `fil:rad`.

## Vad 🔴 Important betyder här

Reservera Important för fynd som bryter beteende, läcker eller exponerar data, eller
försvagar säkerheten:

- API-route saknar autentisering eller org-scoping (cross-tenant-läcka)
- Oinvaliderad användarinput / rå request-åtkomst
- Hårdkodade hemligheter (API-nycklar, JWT-secret)
- Felaktig async-SQLAlchemy-användning som kan ge datakorruption eller blockera loopen
- Klient eller LLM som sätter serverägda fält (id, order, board_order, org_id)
- Logikfel som ger fel resultat i produktion

Stil, namngivning och refaktoreringsförslag är **Nit** som mest.

## Always check (repo-specifikt)

**Backend (`apps/api`):**
- Varje ny/ändrad FastAPI-route ska vara skyddad och org-scopad. Projektrelaterade
  routes använder `Depends(ensure_project_access)`; användarspecifika använder
  `Depends(get_current_user)`. Flagga routes som saknar detta eller som kan returnera
  data över organisationsgränser.
- All request-data valideras via Pydantic-DTO:er i `apps/api/app/dto.py`. Flagga rå/otypad
  request-åtkomst eller saknad validering.
- Nya/ändrade SQLAlchemy-modeller i `apps/api/app/models.py` **måste** ha en motsvarande
  Alembic-migration i `alembic/versions/`. Flagga om migration saknas.
- Nya routrar ska registreras i `apps/api/app/main.py`.
- Hemligheter läses endast via `os.environ` — aldrig hårdkodade.
- Async SQLAlchemy genomgående; inga synkrona session-anrop i async-vägar.

**Agentpipeline (`packages/agents`):**
- LLM-anrop går genom structured output + Pydantic-validering (`call_structured`).
  Flagga fritext-parsning eller regex av modellsvar.
- "Draft"-scheman är LLM-output; mappning till DB-rader sker i `workers/runner.py` och
  ska sätta serverägda fält. Flagga om modellen/LLM:en genererar id eller order.

**Frontend (`apps/web`):**
- Skyddade sidor ska gate:a med `useRequireAuth` och inte rendera förrän `ready`.
- API-anrop går via `apps/web/lib/api.ts` (bifogar JWT). Flagga direkta `fetch()` mot
  backenden som kringgår klienten.
- Återanvänd `components/ui/primitives`; inga duplicerade inline-varianter.
- TypeScript strikt — inget `any`. Datahämtning kräver loading- och error-tillstånd.
- `lib/types.ts` ska hållas i synk med backendens DTO:er. Flagga drift.

## Do not report

- Sådant CI redan fångar: `tsc`, `next build`, `py_compile`.
- `node_modules/`, `.next/`, `*.tsbuildinfo`, lockfiler, genererad kod.
- Ren stil/formatering som en formatter hanterar.
- **SSE-strömmens token-i-query-param** (`/projects/{id}/runs/{run_id}/stream?token=`)
  — medvetet val eftersom `EventSource` inte kan sätta headers. Verifiera ändå att token
  valideras och att org-åtkomst kontrolleras, men flagga inte query-param:en i sig.
- **JWT i localStorage** på frontenden — känd MVP-avvägning, dokumenterad. Flagga inte
  som sårbarhet.

## Nit-volym

Posta som mest 5 Nits per granskning. Hittar du fler, skriv "plus N liknande" i
sammanfattningen i stället för att posta dem inline.

## Verifieringskrav

Beteendepåståenden kräver en `fil:rad`-källa i koden, inte en slutsats från namngivning.

## Re-review

Efter första granskningen: posta endast Important-fynd och håll inne nya Nits.
