/**
 * Tests for the Tactical Scout graphics logic.
 * They check zone mirroring for both teams in both halves, every channel and third, card text, and payoff labels.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  goalPayoffLabel, SCOUT_CARD_MS, SCOUT_ZONE_MS, scoutCardText, scoutFlagFrom, scoutZoneFor, stillVisible, zoneRect,
} from "./scout";
import type { KeyMoment } from "../types";

const THIRD = 35;
const CHANNEL = 68 / 3;

const moment: KeyMoment = {
  moment_id: "m-6", kind: "tactical_pattern", period: 1, match_second: 1850, minute: 31, importance: 0.62,
  team_id: "irv", player_ids: ["kba-03"],
  facts: { pattern: "flank_exposed", team: "Ironvale United", channel: "left", third: "final", count: 6, total: 6,
           share_pct: 100, summary: "Ironvale United beat Felix Tavish down Kestrel Bay Athletic's left flank" },
};

describe("zoneRect", () => {
  it("keeps the home side's frame in the first half and mirrors it in the second", () => {
    const first = zoneRect("left", "final", true, 1);
    expect(first.x).toBeCloseTo(2 * THIRD);
    expect(first.y).toBeCloseTo(0);
    expect(first.width).toBeCloseTo(THIRD);
    expect(first.height).toBeCloseTo(CHANNEL);
    const second = zoneRect("left", "final", true, 2);
    expect(second.x).toBeCloseTo(0);
    expect(second.y).toBeCloseTo(2 * CHANNEL);
  });

  it("mirrors the away side in the first half and keeps it in the second", () => {
    const first = zoneRect("right", "defensive", false, 1);
    expect(first.x).toBeCloseTo(2 * THIRD);
    expect(first.y).toBeCloseTo(0);
    const second = zoneRect("right", "defensive", false, 2);
    expect(second.x).toBeCloseTo(0);
    expect(second.y).toBeCloseTo(2 * CHANNEL);
  });

  it("covers every channel and third with equal non-overlapping bands", () => {
    const channels = ["left", "centre", "right"].map((c) => zoneRect(c, "middle", true, 1));
    expect(channels.map((r) => Math.round(r.y * 100) / 100)).toEqual([0, 22.67, 45.33]);
    const thirds = ["defensive", "middle", "final"].map((t) => zoneRect("centre", t, true, 1));
    expect(thirds.map((r) => Math.round(r.x))).toEqual([0, 35, 70]);
    expect([...channels, ...thirds].every((r) => Math.abs(r.width - THIRD) < 1e-9 && Math.abs(r.height - CHANNEL) < 1e-9)).toBe(true);
  });
});

describe("Scout flag and card", () => {
  it("reads a flag from a tactical moment only", () => {
    const flag = scoutFlagFrom(moment, "31'", 1000);
    expect(flag).toMatchObject({ momentId: "m-6", teamId: "irv", channel: "left", third: "final", count: 6, sharePct: 100 });
    expect(scoutFlagFrom({ ...moment, kind: "goal" }, "31'", 1000)).toBeNull();
  });

  it("writes the card text and colours the zone for the team that benefits", () => {
    const flag = scoutFlagFrom(moment, "31'", 1000)!;
    expect(scoutCardText(flag)).toEqual({ kicker: "TACTICAL SCOUT", headline: "Flank exposed", summary: moment.facts.summary,
                                          stat: "6 entries, 100%", minute: "31'" });
    const zone = scoutZoneFor(flag, "kba", "#home", "#away");
    expect(zone.color).toBe("#away");
    expect(zone.label).toBe("Flank exposed");
    expect(zone.zone.x).toBeCloseTo(0);
  });

  it("shows the card for its duration and the zone for longer", () => {
    expect(SCOUT_ZONE_MS).toBeGreaterThan(SCOUT_CARD_MS);
    expect(stillVisible(1000, 1000 + SCOUT_CARD_MS - 1, SCOUT_CARD_MS)).toBe(true);
    expect(stillVisible(1000, 1000 + SCOUT_CARD_MS, SCOUT_CARD_MS)).toBe(false);
  });
});

describe("goalPayoffLabel", () => {
  it("names the flagged minute and summary, or nothing for an unlinked goal", () => {
    expect(goalPayoffLabel({ flagged_minute: "31'", flagged_summary: "6 of 6 entries" })).toBe("Scout flagged 31': 6 of 6 entries");
    expect(goalPayoffLabel({ scorer: "Mateo Rasmus" })).toBeNull();
  });
});
