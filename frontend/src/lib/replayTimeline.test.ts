/**
 * Tests for instant replay playback timing and interpolation.
 * They check the real-pace build-up, the slow-motion flight, clamping, interpolated positions, and the stage.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  clockAt, motionMs, REPLAY_ANALYSIS_HOLD_MS, REPLAY_BUILDUP_RATE, REPLAY_FLIGHT_RATE, replayLengthMs, replayStage,
  sampleAt, segmentRate,
} from "./replayTimeline";
import type { ReplayKeyframe, TrackingFrame } from "../types";

const key = (phase: ReplayKeyframe["phase"], second: number, ball: [number, number],
  positions: TrackingFrame = []): ReplayKeyframe => ({
  period: 1, match_second: second, phase, event_type: phase === "build_up" ? "pass" : "shot", player_id: "h9",
  receiver_id: null, ball, positions,
});

/** Two build-up actions 2 s apart, the strike 1 s later, and the ball arriving 0.5 s after the strike. */
const frames: ReplayKeyframe[] = [
  key("build_up", 100, [70, 30], [["h9", 70, 30], ["a2", 80, 30]]),
  key("build_up", 102, [80, 32], [["h9", 74, 30], ["h7", 80, 32]]),
  key("shot", 103, [90, 34], [["h9", 90, 34], ["a2", 95, 34]]),
  key("flight", 103.5, [105, 36], [["h9", 90, 34], ["a2", 96, 34]]),
];
const BUILD_UP_MS = 3000;
const FLIGHT_MS = 2000;

describe("replay timeline", () => {
  it("plays the build-up at real pace and the flight in slow motion", () => {
    expect(segmentRate(frames[0])).toBe(REPLAY_BUILDUP_RATE);
    expect(segmentRate(frames[2])).toBe(REPLAY_FLIGHT_RATE);
    expect(motionMs(frames)).toBeCloseTo(BUILD_UP_MS + FLIGHT_MS);
    expect(replayLengthMs(frames)).toBeCloseTo(BUILD_UP_MS + FLIGHT_MS + REPLAY_ANALYSIS_HOLD_MS);
    expect(clockAt(frames, 1500)).toBeCloseTo(101.5);
    expect(clockAt(frames, BUILD_UP_MS + 1000)).toBeCloseTo(103.25);
  });

  it("clamps the clock at the last keyframe and handles no keyframes", () => {
    expect(clockAt(frames, BUILD_UP_MS + FLIGHT_MS + 10_000)).toBe(103.5);
    expect(clockAt(frames, -100)).toBe(100);
    expect(clockAt([], 500)).toBe(0);
  });

  it("puts the ball halfway between the strike and the arrival halfway through the flight", () => {
    const sample = sampleAt(frames, clockAt(frames, BUILD_UP_MS + FLIGHT_MS / 2));
    expect(sample.ball.x).toBeCloseTo(97.5);
    expect(sample.ball.y).toBeCloseTo(35);
    expect(sample.index).toBe(2);
    expect(sample.actor).toBe("h9");
  });

  it("interpolates players and keeps a player missing from one keyframe where the other has them", () => {
    const sample = sampleAt(frames, 101);
    const at = Object.fromEntries(sample.positions.map(([id, x, y]) => [id, [x, y]]));
    expect(at.h9[0]).toBeCloseTo(72);
    expect(at.a2).toEqual([80, 30]);
    expect(at.h7).toEqual([80, 32]);
    expect(sample.ball).toEqual({ x: 75, y: 31 });
  });

  it("holds the last keyframe once the motion ends", () => {
    const sample = sampleAt(frames, 200);
    expect(sample.index).toBe(3);
    expect(sample.ball).toEqual({ x: 105, y: 36 });
  });

  it("moves from build-up to shot to analysis, and stays on analysis until the replay ends", () => {
    expect(replayStage(frames, 0)).toBe("build_up");
    expect(replayStage(frames, BUILD_UP_MS + 10)).toBe("shot");
    expect(replayStage(frames, motionMs(frames))).toBe("analysis");
    expect(replayStage(frames, replayLengthMs(frames) - 1)).toBe("analysis");
  });

  it("plays a story without build-up (strike and flight only) and keyframes that share a second", () => {
    const bare = frames.slice(2);
    expect(motionMs(bare)).toBeCloseTo(FLIGHT_MS);
    expect(replayStage(bare, 0)).toBe("shot");
    expect(sampleAt(bare, clockAt(bare, FLIGHT_MS)).ball).toEqual({ x: 105, y: 36 });
    const same = [frames[0], { ...frames[1], match_second: 100 }, frames[2], frames[3]];
    const sample = sampleAt(same, 100);
    expect(Number.isFinite(sample.ball.x) && Number.isFinite(sample.ball.y)).toBe(true);
    expect(sample.index).toBe(1);
  });
});

