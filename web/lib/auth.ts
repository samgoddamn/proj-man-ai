// Klientsidig sessionslagring. För MVP: token i localStorage. (Överväg
// httpOnly-cookies i produktion för bättre XSS-skydd.)

export interface SessionUser {
  id: string;
  email: string;
  name: string;
}

const TOKEN_KEY = "ai_pm_token";
const USER_KEY = "ai_pm_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as SessionUser) : null;
}

export function setSession(token: string, user: SessionUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
