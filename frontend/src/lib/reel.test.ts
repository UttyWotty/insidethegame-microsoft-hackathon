/**
 * Tests for highlights reel playback timing and the shared player dots.
 * They check frame selection at real pace, clip length with its hold, glide bounds, and action tags.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { MAX_MOVE_MS, MIN_MOVE_MS } from "./motion";
import { playerDots } from "./playerDots";
import { CLIP_HOLD_MS, clipLengthMs, frameBall, frameIndexAt, glideMs } from "./reel";
import type { HighlightClip, HighlightFrame, MatchMetadata } from "../types";

const frame = (second: number, period = 1): HighlightFrame =>
  ({ period, match_second: second, event_type: "pass", player_id: "h1", ball: [10, 20], positions: [["h1", 10, 20]] });
const clip: HighlightClip = {
  moment_id: "m", kind: "goal", minute: "10'", period: 1, match_second: 600, title: "Goal", actor: "A h1", commentary: "In!",
  language: "en", intensity: "peak", frames: [frame(590), frame(592), frame(592.1), frame(600)],
};

describe("reel timing", () => {
  it("shows the last frame at or before the elapsed match time and holds at the end", () => {
    expect(frameIndexAt(clip, 0)).toBe(0);
    expect(frameIndexAt(clip, 2500)).toBe(2);
    expect(frameIndexAt(clip, 60000)).toBe(3);
    expect(clipLengthMs(clip)).toBe(10000 + CLIP_HOLD_MS);
  });

  it("glides over the gap between frames within bounds and maps the ball to the screen", () => {
    expect(glideMs(clip, 0)).toBe(MAX_MOVE_MS);
    expect(glideMs(clip, 1)).toBe(MIN_MOVE_MS);
    expect(frameBall(frame(1, 2))).toEqual({ x: 95, y: 48 });
  });
});

describe("playerDots", () => {
  it("tags the players in the action and shows a sprint speed where given", () => {
    const player = (id: string) => ({ player_id: id, name: `A ${id}`, shirt_number: 1, position: "FW" });
    const match = { home: { players: [player("h1")] }, away: { players: [player("a1")] } } as unknown as MatchMetadata;
    const dots = playerDots(match, { h1: { x: 1, y: 2 }, a1: { x: 3, y: 4 } }, { actor: "h1", receiver: "a1" }, null,
      (id) => (id === "a1" ? 30 : null));
    expect(dots.map((d) => [d.id, d.tagged, d.tagBelow, d.sprintKmh])).toEqual([["h1", true, false, null],
      ["a1", true, true, 30]]);
  });
});
