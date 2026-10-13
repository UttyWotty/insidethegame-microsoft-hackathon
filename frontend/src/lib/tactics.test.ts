/**
 * Tests for the live tactical analysis.
 * They check ends by period, the offside line, team shape, pressure, lane distance, and passing options.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import type { PlayerDot } from "./playerDots";
import { analyseFrame, attacksRight, carrierAfter, chanceBand, distanceToSegment, offsideLine, passChance, shapeBox } from "./tactics";

const dot = (id: string, side: "home" | "away", x: number, y: number, goalkeeper = false): PlayerDot => ({
  id, number: 1, shortName: id, side, position: { x, y }, goalkeeper, tagged: false, tracked: false,
  tagBelow: false, sprintKmh: null,
});
const players = [
  dot("hk", "home", 5, 34, true), dot("h1", "home", 50, 34), dot("h2", "home", 60, 20), dot("h3", "home", 70, 50),
  dot("ak", "away", 100, 34, true), dot("a1", "away", 80, 30), dot("a2", "away", 90, 40), dot("a3", "away", 52, 33),
];

describe("tactics", () => {
  it("knows which way each side attacks", () => {
    expect(attacksRight("home", 1)).toBe(true);
    expect(attacksRight("home", 2)).toBe(false);
    expect(attacksRight("away", 2)).toBe(true);
  });

  it("puts the offside line at the second-deepest defender", () => {
    expect(offsideLine(players, "away", 1)).toBe(90);
    expect(offsideLine(players, "home", 1)).toBe(50);
    expect(offsideLine([dot("x", "home", 1, 1)], "home", 1)).toBeNull();
  });

  it("measures each team's outfield shape", () => {
    expect(shapeBox(players, "home")).toEqual({ x: 50, y: 20, depthM: 20, widthM: 30 });
  });

  it("finds pressure and ranks passing options by completion chance", () => {
    const tactics = analyseFrame(players, "h1", 1);
    expect(tactics.carrier?.pressers).toBe(1);
    expect(tactics.offsideX).toBe(90);
    expect(tactics.shapes.home).toBeNull();
    expect(tactics.shapes.away).toEqual({ x: 52, y: 30, depthM: 38, widthM: 10 });
    expect(analyseFrame(players, null, 1).shapes.home).not.toBeNull();
    expect(tactics.options.map((o) => o.playerId)).toEqual(["h2", "h3"]);
    expect(tactics.options[0].chance).toBeGreaterThan(tactics.options[1].chance);
    expect(analyseFrame(players, null, 1).options).toEqual([]);
  });

  it("hands the ball to a successful pass's receiver", () => {
    expect(carrierAfter({ player_id: "a", receiver_id: "b", outcome: "success", event_type: "pass" })).toBe("b");
    expect(carrierAfter({ player_id: "a", receiver_id: "b", outcome: "failure", event_type: "pass" })).toBe("a");
    expect(carrierAfter(null)).toBeNull();
  });

  it("scores lanes and bands chances", () => {
    expect(distanceToSegment({ x: 5, y: 3 }, { x: 0, y: 0 }, { x: 10, y: 0 })).toBe(3);
    expect(passChance(10, 0)).toBeGreaterThan(passChance(10, 1));
    expect(chanceBand(0.8)).toBe("safe");
    expect(chanceBand(0.6)).toBe("risky");
    expect(chanceBand(0.2)).toBe("unlikely");
  });
});
