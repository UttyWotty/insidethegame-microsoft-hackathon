/**
 * Thin HTTP client for the backend API, reached through the /api prefix.
 * Every call returns typed data or throws ApiError with the server's error detail.
 * The base path is configurable at build time for deployments behind a different host.
 */
import type { ClubInfo, CompanionReply, PersonaInfo, SessionInfo, ViewerSettings } from "../types";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export interface Health { status: string; model_provider: string; sessions: number }
export interface CreateMatch { home: string; away: string; seed: number; speed: number }

export const api = {
  health: () => request<Health>("/health"),
  clubs: () => request<ClubInfo[]>("/clubs"),
  personas: () => request<PersonaInfo[]>("/personas"),
  languages: () => request<Record<string, string>>("/languages"),
  createMatch: (body: CreateMatch) => request<SessionInfo>("/matches", { method: "POST", body: JSON.stringify(body) }),
  ask: (sessionId: string, question: string, viewer: ViewerSettings) =>
    request<CompanionReply>(`/matches/${encodeURIComponent(sessionId)}/ask`, {
      method: "POST", body: JSON.stringify({ question, ...viewer }),
    }),
};

/** URL of the personalized server-sent event stream for one viewer segment. */
export function streamUrl(sessionId: string, viewer: ViewerSettings): string {
  const params = new URLSearchParams({ persona: viewer.persona, language: viewer.language });
  if (viewer.team) params.set("team", viewer.team);
  if (viewer.player) params.set("player", viewer.player);
  return `${API_BASE}/matches/${encodeURIComponent(sessionId)}/stream?${params.toString()}`;
}
