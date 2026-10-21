/**
 * QA tests for the caption placement rule with degenerate measurements and views.
 * A caption measured as NaN, a view too small for any caption, or action markers off the pitch must all fall back
 * to today's full-width lower third rather than throwing or picking a compact corner that does not fit.
 * All logic is pure; the inputs mirror what a half-laid-out or tiny pitch view can report.
 */
import { describe, expect, it } from "vitest";
import { captionPlacement, DEFAULT_CAPTION_PLACEMENT, type CaptionTargets } from "./captionPlacement";

const PHONE_VIEW = { widthPx: 364, heightPx: 261 };
const bottomAction: CaptionTargets = { action: [{ x: 40, y: 62 }, { x: 60, y: 66 }], players: [] };

describe("caption placement with degenerate measurements", () => {
  it("keeps the lower third when the caption heights are not numbers", () => {
    expect(captionPlacement(bottomAction, "tactical", PHONE_VIEW, { fullPx: Number.NaN, compactPx: Number.NaN }))
      .toBe(DEFAULT_CAPTION_PLACEMENT);
  });

  it("keeps the lower third when the view is too small for any caption", () => {
    expect(captionPlacement(bottomAction, "broadcast", { widthPx: 48, heightPx: 40 }, { heightPx: 10, compact: false }))
      .toBe(DEFAULT_CAPTION_PLACEMENT);
  });

  it("keeps the lower third when the full caption is taller than the view", () => {
    expect(captionPlacement(bottomAction, "tactical", PHONE_VIEW, { fullPx: 400, compactPx: 900 }))
      .toBe(DEFAULT_CAPTION_PLACEMENT);
  });
});
