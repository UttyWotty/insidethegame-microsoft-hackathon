/**
 * Tests for pitch coordinate transforms and the broadcast clock.
 * They confirm end swaps at half-time and correct added-time formatting.
 * All functions under test are pure.
 */
import { describe, expect, it } from "vitest";
import { ballAfter, formatClock, minuteLabel, needsMirror, tagPlacement, toScreen } from "./pitch";
import type { MatchEvent } from "../types";

const event = (overrides: Partial<MatchEvent>): MatchEvent => ({
  event_id: "e", sequence: 0, period: 1, match_second: 0, minute: 1, event_type: "pass", team_id: "home",
  player_id: "p", start: { x: 10, y: 20 }, end: null, outcome: null, receiver_id: null, under_pressure: false,
  length_m: null, ball_speed_kmh: null, shot_result: null, score: { home: 0, away: 0 }, ...overrides,
});

describe("pitch transforms", () => {
  it("keeps home first-half coordinates and mirrors away ones", () => {
    expect(needsMirror(true, 1)).toBe(false);
    expect(toScreen({ x: 10, y: 20 }, false, 1)).toEqual({ x: 95, y: 48 });
  });
  it("swaps ends in the second half", () => {
    expect(toScreen({ x: 10, y: 20 }, true, 2)).toEqual({ x: 95, y: 48 });
    expect(toScreen({ x: 10, y: 20 }, false, 2)).toEqual({ x: 10, y: 20 });
  });
  it("prefers the end location for the ball", () => {
    expect(ballAfter(event({ end: { x: 30, y: 30 } }), "home")).toEqual({ x: 30, y: 30 });
    expect(ballAfter(event({ start: null }), "home")).toBeNull();
  });
});

describe("formatClock", () => {
  it("formats regular and added time", () => {
    expect(formatClock(754, 1)).toBe("12:34");
    expect(formatClock(2760, 1)).toBe("45+2'");
    expect(formatClock(5420, 2)).toBe("90+1'");
  });
});

describe("minuteLabel", () => {
  it("labels stoppage time in broadcast style", () => {
    expect(minuteLabel(1330, 1)).toBe("23'");
    expect(minuteLabel(2836, 1)).toBe("45+3'");
    expect(minuteLabel(2700, 2)).toBe("46'");
    expect(minuteLabel(5420, 2)).toBe("90+1'");
  });
});

describe("tagPlacement", () => {
  it("keeps tags inside the frame near every edge", () => {
    expect(tagPlacement({ x: 50, y: 30 }, false)).toEqual({ below: false, anchor: "middle" });
    expect(tagPlacement({ x: 50, y: 2 }, false)).toEqual({ below: true, anchor: "middle" });
    expect(tagPlacement({ x: 50, y: 30 }, true).below).toBe(true);
    expect(tagPlacement({ x: 50, y: 66 }, true).below).toBe(false);
    expect(tagPlacement({ x: 1, y: 30 }, false).anchor).toBe("start");
    expect(tagPlacement({ x: 104, y: 30 }, false).anchor).toBe("end");
  });
});
