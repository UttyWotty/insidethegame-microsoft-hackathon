/**
 * Tests for player motion timing and sprint tags.
 * They check that glides follow the real gap between events within bounds and that sprint tags expire.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { DEFAULT_MOVE_MS, MAX_MOVE_MS, MIN_MOVE_MS, SPRINT_TAG_MS, moveDuration, sprintSpeed } from "./motion";

describe("moveDuration", () => {
  it("glides over the real gap between events, within bounds", () => {
    expect(moveDuration(null, 1000)).toBe(DEFAULT_MOVE_MS);
    expect(moveDuration(1000, 1800)).toBe(800);
    expect(moveDuration(1000, 1010)).toBe(MIN_MOVE_MS);
    expect(moveDuration(1000, 9000)).toBe(MAX_MOVE_MS);
  });
});

describe("sprintSpeed", () => {
  it("shows the speed on the sprinter only, until the tag expires", () => {
    const sprint = { player_id: "p9", speed_kmh: 31.4, at: 1000 };
    expect(sprintSpeed(sprint, "p9", 1500)).toBe(31.4);
    expect(sprintSpeed(sprint, "p4", 1500)).toBeNull();
    expect(sprintSpeed(sprint, "p9", 1000 + SPRINT_TAG_MS + 1)).toBeNull();
    expect(sprintSpeed(null, "p9", 1500)).toBeNull();
  });
});
