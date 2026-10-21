/**
 * Tests for the shot card geometry and labels.
 * They check ball and keeper positions in the goal mouth, blocked shots, and the stat rows.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { ballSpot, GOAL_HEIGHT, GOAL_WIDTH, keeperX, MOUTH_MARGIN_TOP, MOUTH_MARGIN_X, resultLabel, shotStats } from "./shotCard";
import type { ShotCardInfo } from "../types";

const card: ShotCardInfo = { result: "goal", xg: 0.42, speed_kmh: 104.4, distance_m: 12.3, angle_deg: 31.2,
  placement_y: 3, placement_z: 0.4, keeper_y: -1 };

describe("shot card", () => {
  it("places the ball and keeper in the goal mouth as the shooter sees it", () => {
    const spot = ballSpot(card);
    expect(spot?.x).toBeCloseTo(MOUTH_MARGIN_X + GOAL_WIDTH / 2 + 3);
    expect(spot?.y).toBeCloseTo(MOUTH_MARGIN_TOP + GOAL_HEIGHT - 0.4);
    expect(keeperX(card)).toBeCloseTo(MOUTH_MARGIN_X + GOAL_WIDTH / 2 - 1);
    expect(ballSpot({ ...card, placement_y: null, placement_z: null })).toBeNull();
  });

  it("labels the result and lists the stats", () => {
    expect(resultLabel("off_target")).toBe("OFF TARGET");
    expect(shotStats(card).map(([k]) => k)).toEqual(["xG", "Speed", "Distance", "Angle"]);
    expect(shotStats({ ...card, speed_kmh: null }).map(([k]) => k)).toEqual(["xG", "Distance", "Angle"]);
  });
});
