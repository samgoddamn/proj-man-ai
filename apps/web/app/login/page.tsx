"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { Button, Card, Field, Input } from "@/components/ui/primitives";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res =
        mode === "login"
          ? await api.login({ email: form.email, password: form.password })
          : await api.register({ email: form.email, password: form.password, name: form.name });
      setSession(res.access_token, res.user);
      router.push("/");
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-sm space-y-6">
      <h1 className="text-2xl font-bold">{mode === "login" ? "Logga in" : "Skapa konto"}</h1>

      <form onSubmit={onSubmit}>
        <Card className="space-y-4">
          {mode === "register" && (
            <Field label="Namn">
              <Input required value={form.name} onChange={set("name")} />
            </Field>
          )}
          <Field label="E-post">
            <Input required type="email" value={form.email} onChange={set("email")} />
          </Field>
          <Field label="Lösenord">
            <Input
              required
              type="password"
              minLength={8}
              value={form.password}
              onChange={set("password")}
            />
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "…" : mode === "login" ? "Logga in" : "Registrera"}
          </Button>
        </Card>
      </form>

      <p className="text-center text-sm text-slate-500 dark:text-slate-400">
        {mode === "login" ? "Inget konto?" : "Har du redan ett konto?"}{" "}
        <button
          className="font-medium text-brand-600 hover:text-brand-700"
          onClick={() => {
            setMode((m) => (m === "login" ? "register" : "login"));
            setError(null);
          }}
        >
          {mode === "login" ? "Skapa ett" : "Logga in"}
        </button>
      </p>
    </div>
  );
}
