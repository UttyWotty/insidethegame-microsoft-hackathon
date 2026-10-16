/**
 * Tests for choosing how a highlights clip plays: shot clips replay their story, other clips step through frames.
 * They check clip lengths (slow-motion flight plus the caption hold), the story ball at the start, mid-flight and
 * after the motion in the mirrored second half, and that frame clips match the existing reel helpers exactly.
 * All logic is pure, so every clip is built by hand.
 */
import { describe, expect, it } from "vitest";
import { CLIP_HOLD_MS, clipLengthMs, frameBall, frameIndexAt, framePositions, glideMs } from "./reel";
import { reelClipLengthMs, reelView } from "./reelPlayback";
import { motionMs, REPLAY_FLIGHT_RATE } from "./replayTimeline";
import type { HighlightClip, HighlightClipBase, HighlightFrame, ReplayKeyframe } from "../types";

const TICK = 100;
const PERIOD = 2;
const base: HighlightClipBase = {
  moment_id: "m", kind: "goal", minute: "77'", period: PERIOD, match_second: 104, title: "Goal", actor: "A h9",
  commentary: "In!", language: "en", intensity: "peak",
};
const key = (second: number, phase: ReplayKeyframe["phase"], ball: [number, number], receiver: string | null,
  player = "h9"): ReplayKeyframe => ({
  period: PERIOD, match_second: second, phase, event_type: phase === "build_up" ? "pass" : "shot", player_id: player,
  receiver_id: receiver, ball, positions: [["h9", ball[0], ball[1]], ["a1", 50, 34]],
});
const keys = [key(100, "build_up", [10, 20], "h11", "h4"), key(104, "shot", [90, 30], null),
  key(105, "flight", [105, 34], null)];
const story: HighlightClip = { ...base, playback: "story", frames: keys };
const frame = (second: number): HighlightFrame =>
  ({ period: PERIOD, match_second: second, event_type: "pass", player_id: "h1", ball: [10, 20], positions: [["h1", 10, 20]] });
const stepped: HighlightClip = { ...base, playback: "frames", frames: [frame(590), frame(592), frame(592.1), frame(600)] };
const BUILD_UP_MS = 4000;
const FLIGHT_MS = 1000 / REPLAY_FLIGHT_RATE;

describe("reelClipLengthMs", () => {
  it("plays a story's build-up at real pace and its flight in slow motion, then holds", () => {
    expect(reelClipLengthMs(story)).toBe(motionMs(keys) + CLIP_HOLD_MS);
    expect(reelClipLengthMs(story)).toBe(BUILD_UP_MS + FLIGHT_MS + CLIP_HOLD_MS);
  });

  it("keeps the frame clip length for other clips", () => {
    expect(reelClipLengthMs(stepped)).toBe(clipLengthMs(stepped));
  });
});

describe("reelView of a story clip", () => {
  it("starts on the first keyframe's ball, mirrored for the second half", () => {
    expect(reelView(story, 0, TICK)?.ball).toEqual({ x: 95, y: 48 });
    expect(reelView(story, 0, TICK)?.positions.a1).toEqual({ x: 55, y: 34 });
  });

  it("is halfway between the shot and flight balls halfway through the flight", () => {
    const view = reelView(story, BUILD_UP_MS + FLIGHT_MS / 2, TICK);
    expect(view?.ball.x).toBeCloseTo(105 - 97.5);
    expect(view?.ball.y).toBeCloseTo(68 - 32);
  });

  it("holds on the flight ball after the motion", () => {
    expect(reelView(story, BUILD_UP_MS + FLIGHT_MS + CLIP_HOLD_MS, TICK)?.ball).toEqual({ x: 0, y: 34 });
  });

  it("tags the current keyframe's actor and receiver and moves over one tick", () => {
    expect(reelView(story, 1000, TICK)).toMatchObject({ actor: "h4", receiver: "h11", moveMs: TICK });
    expect(reelView(story, BUILD_UP_MS + 10, 250)).toMatchObject({ actor: "h9", receiver: null, moveMs: 250 });
  });
});

describe("reelView of a frame clip", () => {
  it("matches the reel's frame helpers at the frame shown, with no receiver", () => {
    for (const elapsed of [0, 2500, 60000]) {
      const index = frameIndexAt(stepped, elapsed);
      const frame = stepped.frames[index];
      expect(reelView(stepped, elapsed, TICK)).toEqual({
        ball: frameBall(frame), positions: framePositions(frame), actor: frame.player_id, receiver: null,
        moveMs: glideMs(stepped, index),
      });
    }
  });
});

describe("empty clips", () => {
  it("have no view whichever way they play", () => {
    expect(reelView({ ...base, playback: "story", frames: [] }, 0, TICK)).toBeNull();
    expect(reelView({ ...base, playback: "frames", frames: [] }, 0, TICK)).toBeNull();
  });
});
