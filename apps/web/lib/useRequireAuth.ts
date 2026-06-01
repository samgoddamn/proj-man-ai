"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "./auth";

// Skickar till /login om ingen token finns. Returnerar `ready` när det är säkert
// att rendera skyddat innehåll (undviker en flimrande omdirigering vid SSR/hydrering).
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [router]);

  return ready;
}
