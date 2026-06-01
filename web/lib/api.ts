// Typad fetch-klient mot FastAPI-backenden. Allt körs klientsidigt → använder
// den publika API-URL:en.

import { clearSession, getToken, type SessionUser } from "./auth";
import type {
  Board,
  GenerateRequest,
  Project,
  ProjectDetail,
  Task,
  TaskStatus,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignorera parse-fel */
    }
    // Utgången/ogiltig session → rensa lokalt så guarden kan skicka till /login.
    if (res.status === 401) clearSession();
    throw new ApiError(res.status, `${res.status}: ${detail}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: SessionUser;
}

export const api = {
  register: (body: { email: string; password: string; name: string; org_name?: string }) =>
    req<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),

  login: (body: { email: string; password: string }) =>
    req<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),

  listProjects: () => req<Project[]>("/projects"),

  getProject: (id: string) => req<ProjectDetail>(`/projects/${id}`),

  createProject: (body: {
    name: string;
    description: string;
    target_audience?: string;
    business_goals?: string;
    budget?: string;
    timeframe?: string;
  }) => req<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),

  generate: (id: string, body: GenerateRequest) =>
    req<{ run_id: string; status: string }>(`/projects/${id}/generate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getBoard: (id: string) => req<Board>(`/projects/${id}/board`),

  patchTask: (taskId: string, body: Partial<Pick<Task, "status" | "board_order" | "sprint_id">>) =>
    req<Task>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(body) }),

  // SSE-URL för en pågående körning. EventSource kan inte sätta headers, så
  // token skickas som query-param (matchar stream-endpointens auth).
  streamUrl: (projectId: string, runId: string) =>
    `${BASE}/projects/${projectId}/runs/${runId}/stream?token=${encodeURIComponent(getToken() ?? "")}`,
};

export type { TaskStatus };
