"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { Project } from "@/lib/types";
import { Badge, Button, Card } from "@/components/ui/primitives";

const STATUS_TONE: Record<string, string> = {
  draft: "slate",
  generating: "medium",
  ready: "low",
  failed: "high",
};

export default function HomePage() {
  const ready = useRequireAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready) api.listProjects().then(setProjects).catch((e) => setError(String(e)));
  }, [ready]);

  if (!ready) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projekt</h1>
        <Link href="/projects/new">
          <Button>Skapa projekt</Button>
        </Link>
      </div>

      {error && <Card className="text-red-600">Kunde inte ladda projekt: {error}</Card>}

      {projects === null && !error && <p className="text-slate-500 dark:text-slate-400">Laddar…</p>}

      {projects?.length === 0 && (
        <Card className="text-slate-500 dark:text-slate-400">
          Inga projekt än. Skapa ditt första så genererar AI:n hela projektstrukturen.
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {projects?.map((p) => (
          <Link key={p.id} href={`/projects/${p.id}`}>
            <Card className="transition hover:border-brand-400">
              <div className="flex items-start justify-between">
                <h2 className="font-semibold">{p.name}</h2>
                <Badge tone={STATUS_TONE[p.status]}>{p.status}</Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-300">{p.description}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
