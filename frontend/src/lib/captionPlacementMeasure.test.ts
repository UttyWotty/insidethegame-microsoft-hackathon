/**
 * QA tests for how the caption placement treats the caption's last measured height across clips and view sizes.
 * After a compact clip the caption is measured while compact, so the full-width bands must not be judged with the
 * compact caption's taller height, or the next clip stays compact even when a full-width band is clear of its action.
 * All logic is pure and uses the measured sizes of the live phone-width run (a 364 x 261 pitch view).
 */
import { describe, expect, it } from "vitest";
import { captionPlacement, captionRect, type CaptionTargets } from "./captionPlacement";

const PHONE_VIEW = { widthPx: 364, heightPx: 261 };
const FULL_HEIGHT_PX = 112;
const COMPACT_HEIGHT_PX = 298;
const bottomAction: CaptionTargets = {
  action: [{ x: 40, y: 62 }, { x: 50, y: 64 }, { x: 60, y: 66 }],
  players: [],
};

describe("caption placement after a compact clip", () => {
  it("picks the same placement whether the last clip's caption was measured full width or compact", () => {
    const afterFull = captionPlacement(bottomAction, "tactical", PHONE_VIEW, { heightPx: FULL_HEIGHT_PX, compact: false });
    const afterCompact = captionPlacement(bottomAction, "tactical", PHONE_VIEW,
      { heightPx: COMPACT_HEIGHT_PX, compact: true });
    expect(afterFull).toBe("top");
    expect(afterCompact).toBe(afterFull);
  });

  it("does not judge a full-width band with the compact caption's height", () => {
    const full = captionRect("top", PHONE_VIEW, { heightPx: COMPACT_HEIGHT_PX, compact: true });
    expect(full.bottom - full.top).toBeLessThan(COMPACT_HEIGHT_PX);
  });
});
