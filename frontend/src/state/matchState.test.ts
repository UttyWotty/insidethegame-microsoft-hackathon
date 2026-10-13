/**
 * Tests for the stream reducer and active overlay selection.
 * They use hand-built messages shaped exactly like the backend's server-sent events.
 * The reducer is pure, so no DOM or network is needed.
 */
import { describe, expect, it } from "vitest";
import { activeCue, initialMatchState, matchReducer, MOMENTUM_SAMPLE_S, STALE_CUE_MATCH_S, TRAIL_LENGTH } from "./matchState";
import type { EventUpdate, OverlayCue, SessionInfo } from "../types";

const session = {
  session_id: "s", status: "live", speed: 10,
  match: {
    match_id: "m", competition: "c", venue: "v", kickoff_utc: "", seed: 1,
    home: { team_id: "h", name: "Home", short_name: "HOM", style: { label: "x" }, players: [{ player_id: "h-09", name: "Ada Striker", shirt_number: 9, position: "FW" }] },
    away: { team_id: "a", name: "Away", short_name: "AWY", style: { label: "y" }, players: [] },
  },
} as SessionInfo;

const update = (second: number, type = "pass", overrides: Partial<EventUpdate["event"]> = {}): EventUpdate => ({
  event: {
    event_id: `e${second}`, sequence: second, period: 1, match_second: second, minute: Math.floor(second / 60) + 1,
    event_type: type, team_id: "h", player_id: "h-09", start: { x: 50, y: 30 }, end: null, outcome: null,
    receiver_id: null, under_pressure: false, length_m: null, ball_speed_kmh: null, shot_result: null,
    score: { home: 1, away: 0 }, ...overrides,
  },
  xg: null, pass_quality: null, moments: [],
  rhythm: { momentum: 0.4, home_threat: 0.2, away_threat: 0.1, chaos: 0, turnovers_per_minute: 3, home_pass_share: 0.5, state: "balanced" },
});

const cue = (id: string, priority: number, duration = 6): OverlayCue => ({
  cue_id: id, moment_id: id, viewer_id: "v", persona: "casual", language: "en", layout: "lower_third", period: 1,
  display_from_s: 600, duration_s: duration, priority, title: "t", body: "b", stat_callouts: [], commentary: `line ${id}`,
  commentary_language: "en", commentary_intensity: "normal", theme: "control", provenance: {},
});

const withSession = matchReducer(initialMatchState, { type: "message", name: "match", data: session, receivedAt: 0 });

describe("matchReducer", () => {
  it("tracks the ball, a bounded trail, and sampled momentum", () => {
    let state = withSession;
    for (let s = 0; s < 40; s += 1) state = matchReducer(state, { type: "message", name: "event", data: update(s * 5), receivedAt: 0 });
    expect(state.ball).toEqual({ x: 50, y: 30 });
    expect(state.trail).toHaveLength(TRAIL_LENGTH);
    expect(state.momentum).toHaveLength(Math.ceil((39 * 5 + 1) / MOMENTUM_SAMPLE_S));
  });

  it("shows the server's excited goal line once, instead of adding its own", () => {
    let state = matchReducer(withSession, { type: "message", name: "event", data: update(10, "goal"), receivedAt: 0 });
    expect(state.ticker.filter((t) => t.tone === "goal")).toHaveLength(0);
    const goal = { line_id: "e10-pbp", minute: "1'", text: "GOAL! Ada Striker scores!", kind: "goal", intensity: "peak" };
    state = matchReducer(state, { type: "message", name: "commentary", data: goal, receivedAt: 1 });
    expect(state.ticker[0]).toMatchObject({ tone: "goal", intensity: "peak", text: "GOAL! Ada Striker scores!" });
  });

  it("deduplicates cues and recaps", () => {
    let state = matchReducer(withSession, { type: "message", name: "cue", data: cue("c1", 0.5), receivedAt: 1 });
    state = matchReducer(state, { type: "message", name: "cue", data: cue("c1", 0.5), receivedAt: 2 });
    expect(state.cues).toHaveLength(1);
    expect(state.ticker[0].text).toBe("line c1");
  });
});

describe("activeCue", () => {
  it("prefers the highest-priority unexpired cue", () => {
    const cues = [{ cue: cue("low", 0.3), receivedAt: 1000 }, { cue: cue("high", 0.9, 2), receivedAt: 0 }];
    expect(activeCue(cues, 1500)?.cue.cue_id).toBe("high");
    expect(activeCue(cues, 2500)?.cue.cue_id).toBe("low");
    expect(activeCue(cues, 10_000)).toBeNull();
  });
});

describe("activeCue freshness", () => {
  it("never shows replayed history cues as live overlays", () => {
    const replayed = { cue: { ...cue("old", 0.9), replay: true }, receivedAt: 1000 };
    expect(activeCue([replayed], 1500)).toBeNull();
  });
  it("skips cues that are stale against the match clock or from another period", () => {
    const late = { cue: cue("late", 0.9), receivedAt: 1000 };
    expect(activeCue([late], 1500, { period: 1, second: 600 + 100 })?.cue.cue_id).toBe("late");
    expect(activeCue([late], 1500, { period: 1, second: 600 + STALE_CUE_MATCH_S + 10 })).toBeNull();
    expect(activeCue([late], 1500, { period: 2, second: 2800 })).toBeNull();
  });
});

describe("viewer switches and play-by-play", () => {
  it("keeps match-wide state but drops persona-specific state on a viewer switch", () => {
    let state = matchReducer(withSession, { type: "message", name: "event", data: update(30, "goal"), receivedAt: 0 });
    state = matchReducer(state, { type: "message", name: "cue", data: cue("c1", 0.5), receivedAt: 1 });
    const switched = matchReducer(state, { type: "switch-viewer" });
    expect(switched.ticker).toEqual(state.ticker);
    expect(switched.momentum).toEqual(state.momentum);
    expect(switched.cues).toEqual([]);
  });

  it("adds play-by-play lines once and de-duplicates moment commentary across segments", () => {
    const line = { line_id: "e1-pbp", minute: "2'", text: "Kick-off!", kind: "kick_off" };
    let state = matchReducer(withSession, { type: "message", name: "commentary", data: line, receivedAt: 0 });
    state = matchReducer(state, { type: "message", name: "commentary", data: line, receivedAt: 1 });
    state = matchReducer(state, { type: "message", name: "cue", data: { ...cue("seg-a", 0.5), moment_id: "m9" }, receivedAt: 2 });
    state = matchReducer(state, { type: "message", name: "cue", data: { ...cue("seg-b", 0.5), moment_id: "m9" }, receivedAt: 3 });
    expect(state.ticker.filter((t) => t.tone === "play")).toHaveLength(1);
    expect(state.ticker.filter((t) => t.tone === "commentary")).toHaveLength(1);
  });

  it("labels each feed line with the language its text is in, for spoken commentary", () => {
    const line = { line_id: "e1-pbp", minute: "2'", text: "Kick-off!", kind: "kick_off" };
    const spanishCue = { ...cue("seg-es", 0.5), moment_id: "m7", language: "es", commentary_language: "es" };
    let state = matchReducer(withSession, { type: "message", name: "commentary", data: line, receivedAt: 0 });
    state = matchReducer(state, { type: "message", name: "cue", data: spanishCue, receivedAt: 1 });
    expect(state.ticker.find((t) => t.tone === "play")?.language).toBe("en");
    expect(state.ticker.find((t) => t.tone === "commentary")?.language).toBe("es");
  });
});

describe("tracking frames", () => {
  it("places players in the screen frame and swaps ends in the second half", () => {
    const first = { ...update(10), positions: [["h-09", 80, 30]] as [string, number, number][] };
    let state = matchReducer(withSession, { type: "message", name: "event", data: first, receivedAt: 0 });
    expect(state.players["h-09"]).toEqual({ x: 80, y: 30 });
    const second = { ...update(2800), positions: [["h-09", 80, 30]] as [string, number, number][] };
    second.event = { ...second.event, period: 2 };
    state = matchReducer(state, { type: "message", name: "event", data: second, receivedAt: 0 });
    expect(state.players["h-09"]).toEqual({ x: 25, y: 38 });
  });
});

describe("action effects", () => {
  it("records the latest shot trace and goal flash with their arrival time", () => {
    const shot = { ...update(100, "shot", { start: { x: 90, y: 30 }, end: { x: 105, y: 34 }, shot_result: "saved" }), xg: 0.21 };
    let state = matchReducer(withSession, { type: "message", name: "event", data: shot, receivedAt: 500 });
    expect(state.lastShot).toMatchObject({ xg: 0.21, result: "saved", side: "home", at: 500 });
    state = matchReducer(state, { type: "message", name: "event", data: update(101, "goal"), receivedAt: 700 });
    expect(state.goalFlash).toMatchObject({ scorer: "Ada Striker", side: "home", score: "1-0", at: 700 });
  });
});
