/**
 * Tests for projecting pitch points into the 2D pitch view under the tactical and broadcast cameras.
 * The expected pixels were measured in Chromium from static SVG markers on the live pitch in an 894 x 641 view,
 * so the broadcast tilt and perspective here match what the browser draws. All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { projectToView } from "./viewProjection";

const VIEW = { widthPx: 894, heightPx: 641 };
const close = (actual: { x: number; y: number }, x: number, y: number) => {
  expect(actual.x).toBeCloseTo(x, 0);
  expect(actual.y).toBeCloseTo(y, 0);
};

describe("projectToView", () => {
  it("draws the tactical camera flat, runoff included", () => {
    close(projectToView({ x: 0, y: 0 }, "tactical", VIEW), 31.6, 71.2);
    close(projectToView({ x: 105, y: 68 }, "tactical", VIEW), 862.4, 609.2);
    close(projectToView({ x: 52.5, y: 34 }, "tactical", VIEW), 447, 340.2);
  });

  it("tilts the broadcast camera: the far touchline is narrower and lower than flat, the near one wider", () => {
    close(projectToView({ x: 0, y: 0 }, "broadcast", VIEW), 118.2, 157.1);
    close(projectToView({ x: 105, y: 0 }, "broadcast", VIEW), 775.8, 157.1);
    close(projectToView({ x: 0, y: 68 }, "broadcast", VIEW), 59.2, 562.8);
    close(projectToView({ x: 105, y: 68 }, "broadcast", VIEW), 834.8, 562.8);
    close(projectToView({ x: 52.5, y: 34 }, "broadcast", VIEW), 447, 343.2);
  });
});
