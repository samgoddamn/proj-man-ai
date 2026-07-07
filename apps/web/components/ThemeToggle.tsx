"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/primitives";
import { applyTheme, resolveInitialTheme, setStoredTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const initialTheme = resolveInitialTheme();
    applyTheme(initialTheme);
    setTheme(initialTheme);
  }, []);

  const isReady = theme !== null;
  const isDark = theme === "dark";
  const ariaLabel = !isReady ? "Laddar tema" : isDark ? "Byt till ljust läge" : "Byt till mörkt läge";

  return (
    <Button
      type="button"
      variant="ghost"
      aria-label={ariaLabel}
      aria-pressed={isDark}
      disabled={!isReady}
      className="h-10 w-10 p-0 focus-visible:ring-2 focus-visible:ring-brand-500"
      onClick={() => {
        if (!isReady) return;
        const nextTheme: Theme = isDark ? "light" : "dark";
        applyTheme(nextTheme);
        setStoredTheme(nextTheme);
        setTheme(nextTheme);
      }}
    >
      <span aria-hidden="true" className="text-base">
        {!isReady ? "…" : isDark ? "☀️" : "🌙"}
      </span>
    </Button>
  );
}
