/**
 * Tests for the 2D instant replay framing: the crop that contains the whole action and the card's side.
 * They check that a compact action keeps the zoomed crop and that a long build-up and the goal mouth fit with a margin.
 * They also keep the cone in the goal-side half for either goal and long shots, and the crop on the drawn pitch.
 */
import { describe, expect, it } from "vitest";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M, RUNOFF_TOP_M } from "./pitch";
import { type GoalEnd, ZOOM_LENGTH, ZOOM_WIDTH, zoomBox } from "./replay";
import { cardSide, type Crop, REPLAY_MARGIN_M, replayCrop } from "./replayFraming";
import type { Point } from "../types";

const flip = (p: Point): Point => ({ x: PITCH_LENGTH - p.x, y: PITCH_WIDTH - p.y });
/** The 77' winner on screen in the second half: build-up ball points, then the shot origin, attacking the left goal. */
const build = [{ x: 20.4, y: 60.4 }, { x: 6.0, y: 64.4 }, { x: 10.2, y: 30.2 }];
const posts = [{ x: 0, y: 30.34 }, { x: 0, y: 37.66 }];
const landing = { x: 0, y: 32.3 };
const cone = [build[2], ...posts, landing];

function expectInside(crop: Crop, points: Point[]) {
  const [x, y, w, h] = crop;
  for (const p of points) {
    expect(p.x - REPLAY_MARGIN_M).toBeGreaterThanOrEqual(x - 1e-9);
    expect(p.x + REPLAY_MARGIN_M).toBeLessThanOrEqual(x + w + 1e-9);
    expect(p.y - REPLAY_MARGIN_M).toBeGreaterThanOrEqual(y - 1e-9);
    expect(p.y + REPLAY_MARGIN_M).toBeLessThanOrEqual(y + h + 1e-9);
  }
}

function expectGoalHalf(crop: Crop, points: Point[], goal: GoalEnd) {
  const middle = crop[0] + crop[2] / 2;
  for (const p of points) {
    if (goal === "left") expect(p.x + REPLAY_MARGIN_M).toBeLessThanOrEqual(middle + 1e-9);
    else expect(p.x - REPLAY_MARGIN_M).toBeGreaterThanOrEqual(middle - 1e-9);
  }
}

describe("replay framing", () => {
  it("keeps the zoomed crop when the action already fits", () => {
    expect(replayCrop([{ x: 60, y: 30 }, { x: 70, y: 38 }], [], "right")).toEqual(zoomBox({ x: 65, y: 34 }));
  });

  it("frames a long build-up, the goal mouth, and the final ball with a margin, keeping the aspect", () => {
    const action = [...build, ...posts, landing];
    const crop = replayCrop(action, cone, "left");
    expectInside(crop, action);
    expectGoalHalf(crop, cone, "left");
    expect(crop[2] / crop[3]).toBeCloseTo(ZOOM_LENGTH / ZOOM_WIDTH);
    expect(crop[2]).toBeGreaterThanOrEqual(ZOOM_LENGTH);
  });

  it("mirrors for the right goal", () => {
    const action = [...build, ...posts, landing].map(flip);
    const crop = replayCrop(action, cone.map(flip), "right");
    expectInside(crop, action);
    expectGoalHalf(crop, cone.map(flip), "right");
  });

  it("widens for a long shot so the shooter stays in the goal-side half", () => {
    const shooter = { x: 70, y: 40 };
    const action = [shooter, { x: PITCH_LENGTH, y: 30.34 }, { x: PITCH_LENGTH, y: 37.66 }, { x: PITCH_LENGTH, y: 35 }];
    const crop = replayCrop(action, action, "right");
    expectInside(crop, action);
    expectGoalHalf(crop, action, "right");
  });

  it("stays on the drawn pitch and runoff when the action spans the whole pitch", () => {
    const [x, y, w, h] = replayCrop([{ x: 0, y: 0 }, { x: PITCH_LENGTH, y: PITCH_WIDTH }], [{ x: 0, y: 34 }], "left");
    expect(x).toBeGreaterThanOrEqual(-RUNOFF_M);
    expect(y).toBeGreaterThanOrEqual(-RUNOFF_TOP_M);
    expect(x + w).toBeLessThanOrEqual(PITCH_LENGTH + RUNOFF_M + 1e-9);
    expect(y + h).toBeLessThanOrEqual(PITCH_WIDTH + RUNOFF_M + 1e-9);
    expect(w / h).toBeCloseTo(ZOOM_LENGTH / ZOOM_WIDTH);
  });

  it("puts the card on the half away from the attacked goal", () => {
    expect(cardSide("left")).toBe("right");
    expect(cardSide("right")).toBe("left");
  });
});
