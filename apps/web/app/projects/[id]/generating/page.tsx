"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { AgentStatus } from "@/lib/types";
import { Card } from "@/components/ui/primitives";

// Agenter i exekveringsordning, med svenska etiketter.
const AGENTS: { key: string; label: string }[] = [
  { key: "discovery", label: "Discovery — kravanalys" },
  { key: "product_manager", label: "Product Manager — roadmap & epics" },
  { key: "architect", label: "Solution Architect — teknisk arkitektur" },
  { key: "engineering", label: "Engineering — stories & tasks" },
  { key: "scrum_master", label: "Scrum Master — sprintplanering" },
  { key: "qa", label: "QA — teststrategi" },
  { key: "health", label: "Project Health — riskanalys" },
];

type State = Record<string, AgentStatus["status"]>;

export default function GeneratingPage() {
  const ready = useRequireAuth();
  const { id } = useParams<{ id: string }>();
  const runId = useSearchParams().get("run");
  const router = useRouter();
  const [states, setStates] = useState<State>({});
  const [progress, setProgress] = useState(0);
  const [failed, setFailed] = useState<string | null>(null);
  const closed = useRef(false);

  useEffect(() => {
    if (!ready || !runId) return;
    const es = new EventSource(api.streamUrl(id, runId));

    es.onmessage = (ev) => {
      const data: AgentStatus = JSON.parse(ev.data);
      setStates((s) => ({ ...s, [data.agent]: data.status }));
      if (data.progress != null) setProgress(data.progress);
      if (data.status === "failed") setFailed(data.error ?? data.agent);
    };

    // Worker skickar 'event: end' när körningen är klar (eller misslyckats).
    es.addEventListener("end", () => {
      closed.current = true;
      es.close();
      // Liten paus så användaren ser sista bocken, gå sedan till resultatet.
      setTimeout(() => router.push(`/projects/${id}`), 800);
    });

    es.onerror = () => {
      if (!closed.current) setFailed("Anslutningen till statusströmmen bröts.");
      es.close();
    };

    return () => es.close();
  }, [ready, id, runId, router]);

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-bold">Genererar projekt…</h1>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div
          className="h-full bg-brand-600 transition-all duration-500"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>

      <Card className="space-y-3">
        {AGENTS.map((a) => {
          const st = states[a.key];
          const icon = st === "done" ? "✓" : st === "running" ? "⟳" : st === "failed" ? "✕" : "○";
          const color =
            st === "done"
              ? "text-emerald-600"
              : st === "running"
                ? "text-brand-600"
                : st === "failed"
                  ? "text-red-600"
                  : "text-slate-300 dark:text-slate-600";
          return (
            <div key={a.key} className="flex items-center gap-3">
              <span className={`text-lg ${color} ${st === "running" ? "animate-spin" : ""}`}>{icon}</span>
              <span className={st ? "text-slate-900 dark:text-slate-100" : "text-slate-400 dark:text-slate-500"}>
                {a.label}
              </span>
            </div>
          );
        })}
      </Card>

      {failed && (
        <Card className="text-red-600">
          Genereringen misslyckades: {failed}.{" "}
          <button className="underline" onClick={() => router.push(`/projects/${id}`)}>
            Visa projektet ändå
          </button>
        </Card>
      )}
    </div>
  );
}
