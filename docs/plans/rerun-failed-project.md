# Plan: Re-run failed/empty project ("Kör om")

Slug: `rerun-failed-project`
Scope: **Frontend only.** No backend, DTO, model or migration changes. The
`POST /projects/{id}/generate` endpoint already exists and is idempotent
(`apps/api/app/routers/generation.py` → clears prior content via `_clear_previous`,
returns `202` with `{ run_id, status }`).

## Goal
Add a **"Kör om"** button on the project detail view that re-triggers generation,
then navigates to the generating screen.

## Files to touch
- `apps/web/app/projects/[id]/page.tsx` — the only file to change.

No changes needed to `apps/web/lib/api.ts`, `apps/web/lib/types.ts`, or any API file.

## Backend contract (read-only reference)

### Request body — `GenerateRequest` (`apps/api/app/dto.py`)
All fields optional with server-side defaults, but the TS type
`GenerateRequest` (`apps/web/lib/types.ts`) requires all three, so send them explicitly:

| field                 | type | default | bounds        |
|-----------------------|------|---------|---------------|
| `team_size`           | int  | `3`     | 1–20          |
| `sprint_length_weeks` | int  | `2`     | 1–4           |
| `velocity_per_dev`    | int  | `8`     | 1–40          |

**Use these defaults.** No field on the `Project`/`ProjectDetail` object maps to
these sprint parameters (project has only name/description/target_audience/
business_goals/budget/timeframe/status/created_at), so nothing can be pre-filled
from the project — send the constant defaults below.

### Response — `GenerateAccepted`
`{ run_id: string, status: string }` (HTTP 202). The frontend does not need the
body beyond knowing the call succeeded.

### api.ts call (already exists — do not add)
```ts
api.generate(id, { team_size: 3, sprint_length_weeks: 2, velocity_per_dev: 8 })
```
Signature: `generate(id: string, body: GenerateRequest) => Promise<{ run_id: string; status: string }>`

## Visibility condition

`ProjectDetail` fields (from `apps/web/lib/types.ts`):
- `status: "draft" | "generating" | "ready" | "failed"`
- `roadmaps: RoadmapPhase[]`
- `epics: Epic[]`
- `sprints: Sprint[]`
- `risks: Risk[]`
- `architecture: Architecture | null`

Show the button when **(a)** status is `"failed"`, OR **(b)** status is `"ready"`
but all generated content is empty:

```ts
const hasNoContent =
  project.roadmaps.length === 0 &&
  project.epics.length === 0 &&
  project.sprints.length === 0 &&
  project.risks.length === 0 &&
  project.architecture == null;

const canRerun =
  project.status === "failed" ||
  (project.status === "ready" && hasNoContent);
```
(Use `== null` so both `null` and `undefined` architecture count as empty.)

## Behaviour spec

1. Local state in the component: `const [rerunning, setRerunning] = useState(false);`
2. Handler:
   ```ts
   const router = useRouter(); // from "next/navigation"

   async function handleRerun() {
     setRerunning(true);
     try {
       await api.generate(id, {
         team_size: 3,
         sprint_length_weeks: 2,
         velocity_per_dev: 8,
       });
       router.push(`/projects/${id}/generating`);
     } catch (e) {
       setError(String(e));
       setRerunning(false);
     }
   }
   ```
   - Import `useRouter` alongside the existing `useParams` from `next/navigation`.
   - Reuse the existing `setError` state for failures.
   - Keep `rerunning` true on success (navigation unmounts the page).

## Placement

In the header's right-hand action group (`<div className="flex items-center gap-3">`
holding `Badge` and the Kanban `<Link>`), render the re-run button **above** the
Kanban button. Change that container to stack vertically, e.g.
`flex flex-col items-end gap-2`, and render:

```tsx
{canRerun && (
  <Button onClick={handleRerun} disabled={rerunning}>
    {rerunning ? "Startar…" : "Kör om"}
  </Button>
)}
<Link href={`/projects/${id}/kanban`}>
  <Button variant="ghost">Kanban →</Button>
</Link>
```
Keep the `Badge` where it is (it can stay in the same column above both buttons,
or remain in a sibling group — author's discretion, but the **Kör om button must
sit above the Kanban button**). Use the existing `Button` primitive from
`@/components/ui/primitives` (default/non-ghost variant to distinguish it).

## Out of scope
- No sprint-parameter form/modal — fixed defaults only.
- No changes to the `/projects/[id]/generating` page (assumed to already poll/stream the run).
- No new types or api-client methods.
