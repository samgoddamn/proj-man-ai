import type { Metadata } from "next";
import Link from "next/link";
import { HeaderActions } from "@/components/HeaderActions";
import "./globals.css";

const THEME_INIT_SCRIPT = `
(() => {
  const key = "ai_pm_theme";
  const root = document.documentElement;
  let stored = null;
  try {
    stored = window.localStorage.getItem(key);
  } catch {
    stored = null;
  }
  const hasStoredTheme = stored === "light" || stored === "dark";
  const isDark = hasStoredTheme
    ? stored === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.classList.toggle("dark", isDark);
  root.style.colorScheme = isDark ? "dark" : "light";
})();
`;

export const metadata: Metadata = {
  title: "AI Project Manager",
  description: "AI-driven projektledare för produktutveckling",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              AI Project Manager
            </Link>
            <HeaderActions />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
