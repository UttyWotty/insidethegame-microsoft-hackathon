/**
 * Tests for the team-shape graphics logic.
 * They check the shape-shift flash, back lines and label spots in the screen frame for both teams and periods, and
 * the period-aware timeline x mapping.
 * They also check the timeline summary and the analyst stat rows; all logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  blockFor, halfTimeX, lineScreenX, SHAPE_SHIFT_MS, shapeShiftFlash, shapeStatRows, SHIFT_ARROW_Y, shiftLabels,
  timelineAxis, timelinePoints, timelineSummary, timelineX,
} from "./shape";
import { PITCH_WIDTH } from "./pitch";
import type { EventUpdate, KeyMoment, ShapeTimelinePoint, Snapshot, TeamShape } from "../types";

const shiftMoment: KeyMoment = {
  moment_id: "m-12", kind: "shape_shift", period: 2, match_second: 5280, minute: 89, importance: 0.56, team_id: "kba",
  player_ids: [],
  facts: { team: "Kestrel Bay", direction: "dropped", line_before_m: 30.9, line_after_m: 20.2, block_after: "low",
           control_before_pct: 52.7, control_after_pct: 48.2 },
};

const update = (moments: KeyMoment[]): EventUpdate => ({
  event: {
    event_id: "e1", sequence: 1, period: 2, match_second: 5280, minute: 89, event_type: "pass", team_id: "irv",
    player_id: "irv-08", start: { x: 50, y: 30 }, end: null, outcome: "success", receiver_id: null,
    under_pressure: false, length_m: null, ball_speed_kmh: null, shot_result: null, score: { home: 4, away: 3 },
  },
  xg: null, pass_quality: null, moments,
  rhythm: { momentum: 0, home_threat: 0, away_threat: 0, chaos: 0, turnovers_per_minute: 0, home_pass_share: 0.5, state: "balanced" },
});

const point = (minute: number, home: number | null, away: number | null,
               period: number = minute > 45 ? 2 : 1): ShapeTimelinePoint => ({
  period, match_second: (minute - 1) * 60, minute, home_line_m: home, away_line_m: away,
});

const teamShape = (teamId: string, line: number, block: TeamShape["block"]): TeamShape => ({
  team_id: teamId, line_height_m: line, length_m: 45, width_m: 40, compactness_m: 15, block, samples: 40,
  window_minutes: 5,
});

const snapshot = (shape: Snapshot["shape"]): Snapshot => ({
  match_id: "m", period: 2, minute: 89, match_second: 5280, score: { home: 4, away: 3 },
  home: { team_id: "kba", name: "Home", short_name: "HOM", possession_pct: 50, stats: {} },
  away: { team_id: "irv", name: "Away", short_name: "AWY", possession_pct: 50, stats: {} }, rhythm: null, players: {},
  shape,
});

describe("shapeShiftFlash", () => {
  it("is null without a shape_shift moment", () => {
    expect(shapeShiftFlash(update([]), "kba", 100)).toBeNull();
    expect(shapeShiftFlash(update([{ ...shiftMoment, kind: "goal" }]), "kba", 100)).toBeNull();
  });

  it("carries the before and after line, the block, the side, and the arrival time", () => {
    expect(shapeShiftFlash(update([shiftMoment]), "kba", 100)).toEqual({
      momentId: "m-12", teamId: "kba", side: "home", period: 2, lineBeforeM: 30.9, lineAfterM: 20.2, blockAfter: "low",
      at: 100,
    });
    expect(shapeShiftFlash(update([shiftMoment]), "other", 100)?.side).toBe("away");
    expect(SHAPE_SHIFT_MS).toBeGreaterThan(0);
  });
});

describe("lineScreenX", () => {
  it("mirrors the line for home and away in both periods", () => {
    expect(lineScreenX(20, true, 1)).toBe(20);
    expect(lineScreenX(20, true, 2)).toBe(85);
    expect(lineScreenX(20, false, 1)).toBe(85);
    expect(lineScreenX(20, false, 2)).toBe(20);
  });
});

describe("timeline", () => {
  const points = [point(1, null, null), point(10, 28, 30), point(46, null, 31), point(90, 20, 32)];

  it("skips null values and spans the width", () => {
    const lines = timelinePoints(points, 300, 100, timelineAxis(points));
    expect(lines.home.split(" ")).toHaveLength(2);
    expect(lines.away.split(" ")).toHaveLength(3);
    const xs = lines.away.split(" ").map((pair) => Number(pair.split(",")[0]));
    expect(xs[xs.length - 1]).toBe(300);
    expect(Number(lines.home.split(" ")[1].split(",")[1])).toBe(60);
    expect(timelinePoints([point(1, 10, null)], 300, 100, timelineAxis([])).home).toBe("0.0,80.0");
  });

  it("summarises each team's latest line and block", () => {
    expect(timelineSummary(points, "Kestrel Bay", "Ironvale"))
      .toBe("Back-line height per minute. Latest: Kestrel Bay 20.0 m (low block), Ironvale 32.0 m (mid block).");
    expect(timelineSummary([], "A", "B")).toContain("Waiting");
    expect(blockFor(33)).toBe("high");
    expect(blockFor(23.9)).toBe("low");
  });
});

describe("period-aware timeline x", () => {
  it("keeps first-half stoppage minutes before the half-time divider and the second half after it", () => {
    const marks = [point(1, 30, 30), point(45, 30, 30), point(46, 30, 30, 1), point(47, 30, 30, 1),
                   point(46, 30, 30, 2), point(90, 30, 30, 2)];
    const axis = timelineAxis(marks);
    expect(axis).toEqual({ firstHalfEnd: 47, maxSlot: 92 });
    const half = halfTimeX(300, axis);
    const stoppage = timelineX(1, 47, 300, axis);
    const restart = timelineX(2, 46, 300, axis);
    expect(stoppage).toBeLessThan(half);
    expect(restart).toBeGreaterThan(half);
    expect(timelineX(1, 1, 300, axis)).toBe(0);
    expect(timelineX(2, 90, 300, axis)).toBe(300);
  });

  it("matches the plain minute scale when the first half has no stoppage", () => {
    const axis = timelineAxis([point(10, 30, 30), point(80, 30, 30)]);
    expect(axis).toEqual({ firstHalfEnd: 45, maxSlot: 90 });
    expect(timelineX(2, 46, 89, axis)).toBe(45);
    expect(halfTimeX(89, axis)).toBe(44.5);
  });
});

describe("shiftLabels", () => {
  /** The shot card covers roughly the top third of the right side; the offside label sits 1 m above the bottom. */
  const SHOT_CARD_BOTTOM_Y = PITCH_WIDTH / 3;
  const OFFSIDE_LABEL_TOP_Y = PITCH_WIDTH - 1 - 2;

  it("puts every label in the mid-pitch band below the arrow, clear of the shot card and the offside label", () => {
    for (const [before, now] of [[74, 85], [85, 74], [20, 31], [31, 20]]) {
      const labels = shiftLabels(before, now);
      for (const spot of [labels.before, labels.now, labels.block]) {
        expect(spot.y).toBeGreaterThan(SHIFT_ARROW_Y);
        expect(spot.y).toBeGreaterThan(SHOT_CARD_BOTTOM_Y);
        expect(spot.y).toBeLessThan(OFFSIDE_LABEL_TOP_Y);
      }
      expect(labels.block.y).toBeGreaterThan(labels.now.y);
      expect(labels.block.x).toBe(labels.now.x);
    }
  });

  it("writes each label on the outside of its line", () => {
    const right = shiftLabels(74, 85);
    expect([right.before.anchor, right.now.anchor]).toEqual(["end", "start"]);
    expect(right.before.x).toBeLessThan(74);
    expect(right.now.x).toBeGreaterThan(85);
    const left = shiftLabels(85, 74);
    expect([left.before.anchor, left.now.anchor]).toEqual(["start", "end"]);
    expect(left.now.x).toBeLessThan(74);
  });
});

describe("shapeStatRows", () => {
  it("returns no rows without a snapshot shape or before both readings", () => {
    expect(shapeStatRows(snapshot(undefined))).toEqual([]);
    expect(shapeStatRows(snapshot({ home: teamShape("kba", 28, "mid"), away: null }))).toEqual([]);
  });

  it("returns the back line and block rows", () => {
    const rows = shapeStatRows(snapshot({ home: teamShape("kba", 20.2, "low"), away: teamShape("irv", 33.4, "high") }));
    expect(rows.map((r) => r.label)).toEqual(["Back line (m)", "Block"]);
    expect(rows[0].format(rows[0].home)).toBe("20.2");
    expect([rows[1].format(rows[1].home), rows[1].format(rows[1].away)]).toEqual(["Low", "High"]);
  });
});
