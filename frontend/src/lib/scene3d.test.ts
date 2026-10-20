/**
 * Tests for the 3D broadcast view maths.
 * They check coordinate mapping, camera panning limits, smoothing, glides, and facing.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { approach, approachAngle, behindGoalCamera, broadcastCamera, legSwing, STRIDE_ANGLE, CAMERA_PAN_LIMIT, glideAt, heading, pitchToWorld } from "./scene3d";

describe("scene3d", () => {
  it("centres the world on the centre spot", () => {
    expect(pitchToWorld({ x: 52.5, y: 34 })).toEqual({ x: 0, y: 0, z: 0 });
    expect(pitchToWorld({ x: 105, y: 68 }, 2)).toEqual({ x: 52.5, y: 2, z: 34 });
  });

  it("pans the camera with the ball up to a limit", () => {
    expect(broadcastCamera({ x: 62.5, y: 34 }).position.x).toBe(10);
    expect(broadcastCamera({ x: 52.5, y: 34 }).target.z).toBe(3);
    expect(broadcastCamera({ x: 105, y: 34 }).position.x).toBe(CAMERA_PAN_LIMIT);
    expect(broadcastCamera(null).position.x).toBe(0);
  });

  it("puts the replay camera behind the goal the action finished at", () => {
    const right = behindGoalCamera({ x: 95, y: 40 }, "right");
    expect(right.position.x).toBe(66.5);
    expect(right.target).toEqual({ x: 42.5, y: 0, z: 6 });
    expect(behindGoalCamera(null, "left").position.x).toBe(-66.5);
  });

  it("approaches targets smoothly and glides linearly", () => {
    expect(approach(0, 10, 450, 450)).toBeCloseTo(5);
    expect(approach(0, 10, 0, 450)).toBe(0);
    expect(approach(-40, 66.5, Number.POSITIVE_INFINITY, 450)).toBe(66.5);
    const glide = { from: { x: 0, y: 0 }, to: { x: 10, y: 20 }, startedAt: 1000, durationMs: 500 };
    expect(glideAt(glide, 1250)).toEqual({ x: 5, y: 10 });
    expect(glideAt(glide, 5000)).toEqual({ x: 10, y: 20 });
    expect(glideAt({ ...glide, durationMs: 0 }, 0)).toEqual({ x: 10, y: 20 });
  });

  it("swings legs only while running", () => {
    expect(legSwing(Math.PI / 2, true)).toBeCloseTo(STRIDE_ANGLE);
    expect(legSwing(Math.PI / 2, false)).toBe(0);
  });

  it("faces the direction of travel and keeps facing when still", () => {
    expect(heading({ x: 0, y: 0 }, { x: 0, y: 5 })).toBeCloseTo(0);
    expect(heading({ x: 0, y: 0 }, { x: 5, y: 0 })).toBeCloseTo(Math.PI / 2);
    expect(heading({ x: 1, y: 1 }, { x: 1, y: 1 })).toBeNull();
    expect(approachAngle(3.1, -3.1, 1000, 1)).toBeCloseTo(3.1 + (2 * Math.PI - 6.2));
  });
});
