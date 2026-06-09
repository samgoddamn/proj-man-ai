# Code Review: `rerun-failed-project`

**Scope reviewed:** `apps/web/app/projects/[id]/page.tsx` (only code file changed).
**Read for context:** `docs/plans/rerun-failed-project.md`, `apps/web/lib/api.ts`,
`apps/web/lib/types.ts`, `apps/web/components/ui/primitives.tsx`,
`apps/api/app/routers/generation.py`, `apps/api/app/dto.py`.

## Verdict

**No blocker or major issues found.** The implementation matches the plan and the
backend contract. All six review points pass. One minor UX observation is noted
below; it reflects an existing project convention rather than a regression.

---

## Checklist verification

### 1. Visibility condition — ✅ correct
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
- Field names (`roadmaps`, `epics`, `sprints`, `risks`, `architecture`) match
  `ProjectDetail` in `apps/web/lib/types.ts` exactly. The four collections are
  declared as required arrays (and the API DTO defaults them to `[]` via
  `roadmaps: list[RoadmapOut] = []` etc.), so `.length` access is safe.
- `project.architecture == null` correctly treats both `null` and `undefined` as
  empty (loose equality), per the plan.
- The condition is computed **after** the `if (!project) return …` guard, so
  `project` is non-null here — no unsafe access.

### 2. Button placement — ✅ correct
Inside `<div className="flex flex-col items-end gap-2">`, render order is
`Badge` → `Kör om` `<Button>` → Kanban `<Link>`. The "Kör om" button sits
**above** the Kanban button as required. The container was switched to vertical
stacking (`flex flex-col items-end gap-2`) consistent with the plan.

### 3. `api.generate` body — ✅ correct
```ts
await api.generate(id, {
  team_size: 3,
  sprint_length_weeks: 2,
  velocity_per_dev: 8,
});
```
Matches `GenerateRequest` (TS) and the Pydantic `GenerateRequest` DTO. All three
values equal the documented defaults and sit within bounds
(`team_size` 1–20, `sprint_length_weeks` 1–4, `velocity_per_dev` 1–40).

### 4. Navigation only on success — ✅ correct
`router.push(\`/projects/${id}/generating\`)` runs only after `await api.generate(...)`
resolves, inside the `try`. On failure the `catch` runs instead and does not
navigate.

### 5. Loading state / double-submit — ✅ correct
`setRerunning(true)` is set before the call; `<Button disabled={rerunning}>` blocks
re-clicks and the `Button` primitive applies `disabled:opacity-50`. On error
`setRerunning(false)` re-enables; on success `rerunning` is intentionally left
`true` because navigation unmounts the page. Error handling reuses the existing
`setError` state — consistent with the rest of the page.

### 6. No regressions / TS / conventions — ✅ correct
- `useRouter` is imported alongside `useParams` from `next/navigation`; `router`
  is used. No unused imports.
- `canRerun`/`hasNoContent` are derived after the null guard — no early-return
  regression.
- Uses the existing `Button` primitive (default `primary` variant, distinguishing
  it from the ghost Kanban button) — matches conventions.
- Pre-existing `Badge` tone logic is untouched.

---

## Minor / Nit

### Nit — a failed re-run hides the entire project view
`handleRerun`'s `catch` calls `setError(String(e))`, and the page has an
early return:
```ts
if (error) return <Card className="text-red-600">{error}</Card>;
```
So if `api.generate` fails (e.g. the backend returns `409 "Generering pågår
redan"` due to a race, or a network error), the whole project detail screen is
replaced by a bare error card with no way to dismiss it short of a reload.

This is **consistent with the existing pattern** (the `getProject` failure path
does the same), so it is not a regression and not blocking. If inline,
dismissible error feedback is desired later, that would be a page-wide
improvement rather than something specific to this feature.

No fix required for this feature.
