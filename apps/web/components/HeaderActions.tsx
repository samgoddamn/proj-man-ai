"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { clearSession, getUser, type SessionUser } from "@/lib/auth";

export function HeaderActions() {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);

  // Läs sessionen efter mount (localStorage finns inte under SSR).
  useEffect(() => setUser(getUser()), []);

  if (!user) {
    return (
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <Link href="/login" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          Logga in
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4 text-sm">
      <ThemeToggle />
      <Link href="/projects/new" className="font-medium text-brand-600 hover:text-brand-700">
        + Nytt projekt
      </Link>
      <span className="text-slate-500 dark:text-slate-400">{user.name}</span>
      <button
        type="button"
        className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
        onClick={() => {
          clearSession();
          router.replace("/login");
        }}
      >
        Logga ut
      </button>
    </div>
  );
}
