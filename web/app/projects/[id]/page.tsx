"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { ProjectDetail } from "@/lib/types";
import { Badge, Button, Card } from "@/components/ui/primitives";

const TABS = ["Roadmap", "Epics", "Sprintar", "Arkitektur", "Risker"] as const;
type Tab = (typeof TABS)[number];

export default function ProjectPage() {
  const ready = useRequireAuth();
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Roadmap");

  useEffect(() => {
    if (ready) api.getProject(id).then(setProject).catch((e) => setError(String(e)));
  }, [ready, id]);

  if (!ready) return null;
  if (error) return <Card className="text-red-600">{error}</Card>;
  if (!project) return <p className="text-slate-500">Laddar…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="mt-1 max-w-2xl text-slate-600">{project.description}</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone={project.status === "ready" ? "low" : "medium"}>{project.status}</Badge>
          <Link href={`/projects/${id}/kanban`}>
            <Button variant="ghost">Kanban →</Button>
          </Link>
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={
              "px-4 py-2 text-sm font-medium " +
              (tab === t
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-slate-500 hover:text-slate-800")
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
                {r.summary && <p className="mt-1 text-sm text-slate-600">{r.summary}</p>}
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
              {e.description && <p className="text-sm text-slate-600">{e.description}</p>}
              <div className="space-y-2 border-l-2 border-slate-100 pl-4">
                {e.stories.map((s) => (
                  <div key={s.id}>
                    <p className="text-sm">
                      <span className="text-slate-400">Som</span> {s.role}{" "}
                      <span className="text-slate-400">vill jag</span> {s.want}{" "}
                      <span className="text-slate-400">så att</span> {s.so_that}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {s.tasks.map((t) => (
                        <span key={t.id} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
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
                  <span className="text-sm text-slate-500">
                    {s.capacity_points}p · {s.start_date} → {s.end_date}
                  </span>
                </div>
                {s.goal && <p className="mt-1 text-sm text-slate-600">{s.goal}</p>}
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
              <Card className="text-sm text-slate-600">{project.architecture.rationale}</Card>
            )}
          </div>
        ) : (
          <p className="text-slate-500">Ingen arkitektur genererad än.</p>
        ))}

      {tab === "Risker" && (
        <div className="space-y-3">
          {project.risks.length === 0 && <p className="text-slate-500">Inga risker identifierade.</p>}
          {project.risks.map((r) => (
            <Card key={r.id} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{r.title}</span>
                <Badge tone={r.severity}>{r.severity}</Badge>
              </div>
              {r.description && <p className="text-sm text-slate-600">{r.description}</p>}
              {r.recommendation && (
                <p className="text-sm text-brand-700">→ {r.recommendation}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
