/**
 * Pure reducer folding server-sent stream messages into the UI's match state.
 * It tracks the ball and recent trail, sampled momentum, received overlay cues, a commentary ticker, and recaps.
 * Wall-clock time arrives inside actions so the reducer stays deterministic and testable.
 */
import { ballAfter, minuteLabel, toScreen } from "../lib/pitch";
import type {
  EventUpdate, MatchEvent, OverlayCue, Point, Recap, Rhythm, SessionInfo, Snapshot,
} from "../types";

export const TRAIL_LENGTH = 14;
export const MOMENTUM_SAMPLE_S = 30;
export const MAX_CUES = 40;
export const MAX_TICKER = 40;
export const STALE_CUE_MATCH_S = 300;
const TICKER_EVENT_TYPES = new Set(["goal", "save", "shot"]);

export type MessageName = "match" | "event" | "snapshot" | "cue" | "commentary" | "recap" | "end";

export interface TrailPoint extends Point { side: "home" | "away"; type: string; id: string }
export interface MomentumPoint { second: number; period: number; momentum: number }
export interface ReceivedCue { cue: OverlayCue; receivedAt: number }
export interface TickerItem { id: string; minute: string; text: string; tone: "commentary" | "goal" | "info" | "play" }
export interface PlayLine { line_id: string; minute: string; text: string; kind: string }

export interface MatchState {
  session: SessionInfo | null;
  snapshot: Snapshot | null;
  lastEvent: MatchEvent | null;
  ball: Point | null;
  players: Record<string, Point>;
  trail: TrailPoint[];
  rhythm: Rhythm | null;
  momentum: MomentumPoint[];
  cues: ReceivedCue[];
  ticker: TickerItem[];
  recaps: Recap[];
  ended: boolean;
}

export type StreamAction =
  | { type: "message"; name: MessageName; data: unknown; receivedAt: number }
  | { type: "reset" }
  | { type: "switch-viewer" };

export const initialMatchState: MatchState = {
  session: null, snapshot: null, lastEvent: null, ball: null, players: {}, trail: [], rhythm: null, momentum: [], cues: [],
  ticker: [], recaps: [], ended: false,
};

function playerName(state: MatchState, playerId: string | null): string {
  const match = state.session?.match;
  if (!match || !playerId) return "";
  const player = [...match.home.players, ...match.away.players].find((p) => p.player_id === playerId);
  return player?.name ?? "";
}

function eventTicker(state: MatchState, event: MatchEvent): TickerItem | null {
  if (!TICKER_EVENT_TYPES.has(event.event_type)) return null;
  const name = playerName(state, event.player_id);
  const minute = minuteLabel(event.match_second, event.period);
  if (event.event_type === "goal") {
    return { id: event.event_id, minute, text: `GOAL - ${name}. ${event.score.home}-${event.score.away}`, tone: "goal" };
  }
  if (event.event_type === "save") return { id: event.event_id, minute, text: `Save by ${name}`, tone: "info" };
  if (event.shot_result === "goal") return null;
  const result = (event.shot_result ?? "").replace("_", " ");
  return { id: event.event_id, minute, text: `Shot by ${name} (${result})`, tone: "info" };
}

function applyEvent(state: MatchState, update: EventUpdate): MatchState {
  const event = update.event;
  const homeId = state.session?.match.home.team_id ?? "";
  const ball = ballAfter(event, homeId) ?? state.ball;
  const trail = ball && event.team_id
    ? [...state.trail, { ...ball, side: event.team_id === homeId ? "home" : "away", type: event.event_type, id: event.event_id } as TrailPoint]
        .slice(-TRAIL_LENGTH)
    : state.trail;
  const last = state.momentum[state.momentum.length - 1];
  const sample = !last || last.period !== event.period || event.match_second - last.second >= MOMENTUM_SAMPLE_S;
  const momentum = sample
    ? [...state.momentum, { second: event.match_second, period: event.period, momentum: update.rhythm.momentum }]
    : state.momentum;
  const item = eventTicker(state, event);
  const ticker = item ? addTicker(state, item) : state.ticker;
  const players = update.positions
    ? Object.fromEntries(update.positions.map(([id, x, y]) => [id, toScreen({ x, y }, true, event.period)]))
    : state.players;
  return { ...state, lastEvent: event, ball, players, trail, rhythm: update.rhythm, momentum, ticker };
}

function addTicker(state: MatchState, item: TickerItem): TickerItem[] {
  if (state.ticker.some((t) => t.id === item.id)) return state.ticker;
  return [item, ...state.ticker].slice(0, MAX_TICKER);
}

function applyCue(state: MatchState, cue: OverlayCue, receivedAt: number): MatchState {
  if (state.cues.some((c) => c.cue.cue_id === cue.cue_id)) return state;
  const minute = minuteLabel(cue.display_from_s, cue.period);
  const commentary: TickerItem = { id: `moment-${cue.moment_id}`, minute, text: cue.commentary, tone: "commentary" };
  return { ...state, cues: [{ cue, receivedAt }, ...state.cues].slice(0, MAX_CUES), ticker: addTicker(state, commentary) };
}

/** Keep match-wide state when the viewer changes persona or language; drop only persona-specific state. */
function switchViewer(state: MatchState): MatchState {
  return { ...state, cues: [], recaps: [], ended: false };
}

/** Fold one action into the match state. */
export function matchReducer(state: MatchState, action: StreamAction): MatchState {
  if (action.type === "reset") return initialMatchState;
  if (action.type === "switch-viewer") return switchViewer(state);
  switch (action.name) {
    case "match": return { ...state, session: action.data as SessionInfo };
    case "snapshot": return { ...state, snapshot: action.data as Snapshot };
    case "event": return applyEvent(state, action.data as EventUpdate);
    case "cue": return applyCue(state, action.data as OverlayCue, action.receivedAt);
    case "commentary": {
      const line = action.data as PlayLine;
      return { ...state, ticker: addTicker(state, { id: line.line_id, minute: line.minute, text: line.text, tone: "play" }) };
    }
    case "recap": {
      const recap = action.data as Recap;
      return state.recaps.some((r) => r.stage === recap.stage) ? state : { ...state, recaps: [...state.recaps, recap] };
    }
    case "end": return { ...state, ended: true };
  }
}

export interface MatchClock { period: number; second: number }

function isCurrent(cue: OverlayCue, clock: MatchClock | null): boolean {
  if (cue.replay) return false;
  if (!clock) return true;
  return cue.period === clock.period && clock.second - cue.display_from_s <= STALE_CUE_MATCH_S;
}

/** The overlay to show now: the most important live cue within its display window and near the match clock. */
export function activeCue(cues: ReceivedCue[], now: number, clock: MatchClock | null = null): ReceivedCue | null {
  const live = cues.filter((c) => isCurrent(c.cue, clock) && now - c.receivedAt < c.cue.duration_s * 1000);
  return live.sort((a, b) => b.cue.priority - a.cue.priority || b.receivedAt - a.receivedAt)[0] ?? null;
}
