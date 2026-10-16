/**
 * Thin HTTP client for the backend API, reached through the /api prefix.
 * Every call returns typed data or throws ApiError with the server's error detail.
 * The base path is configurable at build time for deployments behind a different host.
 */
import type {
  ClubInfo, CompanionReply, HighlightReel, PersonaInfo, ProducerSummary, ReplayStory, SessionInfo, StudioPayload,
  ViewerSettings,
} from "../types";

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
  speechStatus: () => request<{ available: boolean }>("/speech/status"),
  speechUrl: (sessionId: string, ref: string, segment?: string) => {
    const query = new URLSearchParams({ ref, ...(segment ? { segment } : {}) });
    return `${API_BASE}/matches/${encodeURIComponent(sessionId)}/speech?${query}`;
  },
  clubs: () => request<ClubInfo[]>("/clubs"),
  personas: () => request<PersonaInfo[]>("/personas"),
  languages: () => request<Record<string, string>>("/languages"),
  createMatch: (body: CreateMatch) => request<SessionInfo>("/matches", { method: "POST", body: JSON.stringify(body) }),
  highlights: (sessionId: string, stage: HighlightReel["stage"], segment?: string) => {
    const query = new URLSearchParams({ stage, ...(segment ? { segment } : {}) });
    return request<HighlightReel>(`/matches/${encodeURIComponent(sessionId)}/highlights?${query}`);
  },
  replay: (sessionId: string, period: number, at: number) =>
    request<ReplayStory>(`/matches/${encodeURIComponent(sessionId)}/replay?period=${period}&at=${at}`),
  studio: (sessionId: string, window: StudioPayload["window"]) =>
    request<StudioPayload>(`/matches/${encodeURIComponent(sessionId)}/studio?window=${window}`),
  producer: (sessionId: string) => request<ProducerSummary>(`/matches/${encodeURIComponent(sessionId)}/producer`),
  hold: (sessionId: string, on: boolean) =>
    request<{ hold: boolean }>(`/matches/${encodeURIComponent(sessionId)}/producer/hold`, {
      method: "POST", body: JSON.stringify({ on }),
    }),
  release: (sessionId: string, momentId: string | null) =>
    request<{ released_cues: number }>(`/matches/${encodeURIComponent(sessionId)}/producer/release`, {
      method: "POST", body: JSON.stringify({ moment_id: momentId }),
    }),
  ask: (sessionId: string, question: string, viewer: ViewerSettings) =>
    request<CompanionReply>(`/matches/${encodeURIComponent(sessionId)}/ask`, {
      method: "POST", body: JSON.stringify({ question, ...viewer }),
    }),
};

/** URL of the producer console's server-sent event stream for one session. */
export function producerStreamUrl(sessionId: string): string {
  return `${API_BASE}/matches/${encodeURIComponent(sessionId)}/producer/stream`;
}

/** URL of the personalized server-sent event stream for one viewer segment. */
export function streamUrl(sessionId: string, viewer: ViewerSettings): string {
  const params = new URLSearchParams({ persona: viewer.persona, language: viewer.language });
  if (viewer.team) params.set("team", viewer.team);
  if (viewer.player) params.set("player", viewer.player);
  return `${API_BASE}/matches/${encodeURIComponent(sessionId)}/stream?${params.toString()}`;
}
