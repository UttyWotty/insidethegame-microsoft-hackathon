/**
 * Tests for studio visual geometry and wording.
 * They check grid rectangles, bounded network sizes, and the space control summary.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { cellRects, describeControl, heatFill, linkWidth, nodeRadius } from "./studio";

describe("studio geometry", () => {
  it("lays grid cells across the pitch", () => {
    const rects = cellRects([[0, 1], [0.5, 0]]);
    expect(rects).toHaveLength(4);
    expect(rects[1]).toEqual({ x: 52.5, y: 0, w: 52.5, h: 34, value: 1 });
  });

  it("colours heat from pale yellow to red", () => {
    expect(heatFill(0)).toEqual({ color: "rgb(253, 224, 71)", opacity: 0.3 });
    expect(heatFill(1).color).toBe("rgb(239, 68, 68)");
    expect(heatFill(1).opacity).toBeCloseTo(0.85);
    expect(heatFill(2).color).toBe("rgb(239, 68, 68)");
  });

  it("sizes network nodes and links within bounds", () => {
    expect(nodeRadius(0)).toBeCloseTo(1.4);
    expect(nodeRadius(500)).toBe(4);
    expect(linkWidth(100)).toBe(1.6);
  });

  it("summarises space control like a pundit", () => {
    const text = describeControl({ owners: [], home_share: 42, home_thirds: [80, 40, 10] }, "Kestrel", "Ironvale");
    expect(text).toBe("Ironvale control 58% of the pitch right now; Kestrel own most of their defensive third (80%).");
  });
});
