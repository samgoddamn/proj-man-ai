import type { Metadata } from "next";
import Link from "next/link";
import { HeaderActions } from "@/components/HeaderActions";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Project Manager",
  description: "AI-driven projektledare för produktutveckling",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-semibold">
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
