"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { ProjectDetail } from "@/lib/types";
import { Badge, Button, Card } from "@/components/ui/primitives";

const TABS = ["Roadmap", "Epics", "Sprintar", "Arkitektur", "Risker"] as const;
type Tab = (typeof TABS)[number];

export default function ProjectPage() {
  const ready = useRequireAuth();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Roadmap");
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    if (ready) api.getProject(id).then(setProject).catch((e) => setError(String(e)));
  }, [ready, id]);

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

  if (!ready) return null;
  if (error) return <Card className="text-red-600">{error}</Card>;
  if (!project) return <p className="text-slate-500 dark:text-slate-400">Laddar…</p>;

  const hasNoContent =
    project.roadmaps.length === 0 &&
    project.epics.length === 0 &&
    project.sprints.length === 0 &&
    project.risks.length === 0 &&
    project.architecture == null;

  const canRerun =
    project.status === "failed" ||
    (project.status === "ready" && hasNoContent);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="mt-1 max-w-2xl text-slate-600 dark:text-slate-300">{project.description}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge tone={project.status === "ready" ? "low" : "medium"}>{project.status}</Badge>
          {canRerun && (
            <Button onClick={handleRerun} disabled={rerunning}>
              {rerunning ? "Startar…" : "Kör om"}
            </Button>
          )}
          <Link href={`/projects/${id}/kanban`}>
            <Button variant="ghost">Kanban →</Button>
          </Link>
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={
              "px-4 py-2 text-sm font-medium " +
              (tab === t
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200")
            }
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Roadmap" && (
        <div className="space-y-3">
          {project.roadmaps
            .sort((a, b) => a.phase - b.phase)
            .map((r) => (
              <Card key={r.id}>
                <div className="font-semibold">
                  Fas {r.phase}: {r.title}
                </div>
                {r.summary && <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{r.summary}</p>}
              </Card>
            ))}
        </div>
      )}

      {tab === "Epics" && (
        <div className="space-y-4">
          {project.epics.map((e) => (
            <Card key={e.id} className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="font-semibold">{e.title}</div>
                <Badge tone={e.priority}>{e.priority}</Badge>
              </div>
              {e.description && <p className="text-sm text-slate-600 dark:text-slate-300">{e.description}</p>}
              <div className="space-y-2 border-l-2 border-slate-100 pl-4 dark:border-slate-800">
                {e.stories.map((s) => (
                  <div key={s.id}>
                    <p className="text-sm">
                      <span className="text-slate-400 dark:text-slate-500">Som</span> {s.role}{" "}
                      <span className="text-slate-400 dark:text-slate-500">vill jag</span> {s.want}{" "}
                      <span className="text-slate-400 dark:text-slate-500">så att</span> {s.so_that}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {s.tasks.map((t) => (
                        <span
                          key={t.id}
                          className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                        >
                          {t.title} · {t.estimate}p
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === "Sprintar" && (
        <div className="space-y-3">
          {project.sprints
            .sort((a, b) => a.order - b.order)
            .map((s) => (
              <Card key={s.id}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-sm text-slate-500 dark:text-slate-400">
                    {s.capacity_points}p · {s.start_date} → {s.end_date}
                  </span>
                </div>
                {s.goal && <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.goal}</p>}
              </Card>
            ))}
        </div>
      )}

      {tab === "Arkitektur" &&
        (project.architecture ? (
          <div className="space-y-4">
            <Card>
              <h3 className="mb-2 font-semibold">Teknikstack</h3>
              <ul className="space-y-1 text-sm">
                {project.architecture.stack.map((s, i) => (
                  <li key={i}>
                    <span className="font-medium">{s.layer}:</span> {s.technology} — {s.rationale}
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <h3 className="mb-2 font-semibold">Datamodell</h3>
              <ul className="space-y-1 text-sm">
                {project.architecture.data_model.map((d, i) => (
                  <li key={i}>
                    <span className="font-medium">{d.name}</span> ({d.fields.join(", ")})
                  </li>
                ))}
              </ul>
            </Card>
            {project.architecture.rationale && (
              <Card className="text-sm text-slate-600 dark:text-slate-300">{project.architecture.rationale}</Card>
            )}
          </div>
        ) : (
          <p className="text-slate-500 dark:text-slate-400">Ingen arkitektur genererad än.</p>
        ))}

      {tab === "Risker" && (
        <div className="space-y-3">
          {project.risks.length === 0 && <p className="text-slate-500 dark:text-slate-400">Inga risker identifierade.</p>}
          {project.risks.map((r) => (
            <Card key={r.id} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{r.title}</span>
                <Badge tone={r.severity}>{r.severity}</Badge>
              </div>
              {r.description && <p className="text-sm text-slate-600 dark:text-slate-300">{r.description}</p>}
              {r.recommendation && (
                <p className="text-sm text-brand-700 dark:text-brand-300">→ {r.recommendation}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
