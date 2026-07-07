"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { Button, Card, Field, Input, Textarea } from "@/components/ui/primitives";

export default function NewProjectPage() {
  const ready = useRequireAuth();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    target_audience: "",
    business_goals: "",
    budget: "",
    timeframe: "",
  });
  const [team, setTeam] = useState({ team_size: 3, sprint_length_weeks: 2, velocity_per_dev: 8 });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // 1. Skapa draft. 2. Trigga pipeline. 3. Hoppa till live-genereringsvyn.
      const project = await api.createProject({
        name: form.name,
        description: form.description,
        target_audience: form.target_audience || undefined,
        business_goals: form.business_goals || undefined,
        budget: form.budget || undefined,
        timeframe: form.timeframe || undefined,
      });
      const { run_id } = await api.generate(project.id, team);
      router.push(`/projects/${project.id}/generating?run=${run_id}`);
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Nytt projekt</h1>
      <p className="text-slate-600 dark:text-slate-300">
        Beskriv idén — AI:n genererar roadmap, epics, user stories, tasks, sprintar och riskanalys.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <Card className="space-y-4">
          <Field label="Projektnamn *">
            <Input required value={form.name} onChange={set("name")} placeholder="HandyHub" />
          </Field>
          <Field label="Beskrivning *">
            <Textarea
              required
              rows={4}
              value={form.description}
              onChange={set("description")}
              placeholder="En plattform där privatpersoner kan hitta och boka hantverkare."
            />
          </Field>
          <Field label="Målgrupp">
            <Input value={form.target_audience} onChange={set("target_audience")} placeholder="Privatpersoner och hantverkare" />
          </Field>
          <Field label="Affärsmål">
            <Input value={form.business_goals} onChange={set("business_goals")} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Budget (valfritt)">
              <Input value={form.budget} onChange={set("budget")} />
            </Field>
            <Field label="Tidsram (valfritt)">
              <Input value={form.timeframe} onChange={set("timeframe")} placeholder="MVP inom 3 mån" />
            </Field>
          </div>
        </Card>

        <Card className="space-y-4">
          <h2 className="font-semibold">Sprintplanering</h2>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Teamstorlek">
              <Input
                type="number"
                min={1}
                value={team.team_size}
                onChange={(e) => setTeam((t) => ({ ...t, team_size: Number(e.target.value) }))}
              />
            </Field>
            <Field label="Sprintlängd (v)">
              <Input
                type="number"
                min={1}
                max={4}
                value={team.sprint_length_weeks}
                onChange={(e) => setTeam((t) => ({ ...t, sprint_length_weeks: Number(e.target.value) }))}
              />
            </Field>
            <Field label="Velocity/dev">
              <Input
                type="number"
                min={1}
                value={team.velocity_per_dev}
                onChange={(e) => setTeam((t) => ({ ...t, velocity_per_dev: Number(e.target.value) }))}
              />
            </Field>
          </div>
        </Card>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" disabled={submitting}>
          {submitting ? "Skapar…" : "Generera projekt"}
        </Button>
      </form>
    </div>
  );
}
