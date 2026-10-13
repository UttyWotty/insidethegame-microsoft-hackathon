/**
 * Tests for instant replay rules.
 * They check which shots earn a replay, which goal the camera sits behind, the zoom crop, and line rotation.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { earnsReplay, goalEnd, replayLine, zoomBox } from "./replay";
import type { ShotTrace } from "../state/matchState";
import type { HighlightFrame } from "../types";

const shot = (result: string, xg: number | null): ShotTrace => ({
  id: "e1", from: { x: 90, y: 30 }, to: { x: 105, y: 34 }, xg, result, side: "home", at: 0, period: 1, second: 600,
  shooter: "h9",
});
const frame = (x: number, period = 1): HighlightFrame =>
  ({ period, match_second: 0, event_type: "shot", player_id: null, ball: [x, 34], positions: [] });

describe("replay rules", () => {
  it("replays every goal and only big chances otherwise", () => {
    expect(earnsReplay(shot("goal", 0.05))).toBe(true);
    expect(earnsReplay(shot("saved", 0.3))).toBe(true);
    expect(earnsReplay(shot("off_target", 0.1))).toBe(false);
    expect(earnsReplay(shot("blocked", null))).toBe(false);
  });

  it("puts the camera behind the goal where the action ends, in screen space", () => {
    expect(goalEnd([frame(100)])).toBe("right");
    expect(goalEnd([frame(100, 2)])).toBe("left");
  });

  it("crops around the action inside the pitch and varies the line", () => {
    expect(zoomBox({ x: 100, y: 34 })).toEqual([53, 17, 52, 34]);
    expect(zoomBox({ x: 5, y: 2 })).toEqual([0, 0, 52, 34]);
    expect(["Let's see that again.", "Here it is once more.", "Watch this again.", "One more look at that."])
      .toContain(replayLine(shot("goal", 0.4)));
  });
});
