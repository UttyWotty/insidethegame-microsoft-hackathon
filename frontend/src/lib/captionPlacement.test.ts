/**
 * Tests for placing the highlights caption clear of a story clip's action on the tactical and broadcast cameras.
 * They cover action at the bottom, at the top, and spread over the pitch, the players tie-break, the fit-inside-view
 * rule and its full-width fallback, per-layout heights, the defaults for frame clips, the 3D camera and an unmeasured
 * view, and the targets a story clip yields. All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  captionPlacement, captionRect, CAPTION_INSET_Y_PX, type CaptionTargets, DEFAULT_CAPTION_PLACEMENT, layoutHeights,
  storyTargets,
} from "./captionPlacement";
import { reelClipLengthMs } from "./reelPlayback";
import type { HighlightClip, HighlightClipBase, ReplayKeyframe } from "../types";

const VIEW = { widthPx: 894, heightPx: 641 };
const CAPTION = { heightPx: 112, compact: false };
const TALL_CAPTION = { heightPx: 200, compact: false };
const TICK = 100;
/** The live phone-width pitch view and the measured heights there (QA round 1, 390 x 844 viewport). */
const PHONE_VIEW = { widthPx: 364, heightPx: 261 };
const PHONE_HEIGHTS = { fullPx: 112, compactPx: 298 };
const base: HighlightClipBase = {
  moment_id: "m", kind: "goal", minute: "65'", period: 1, match_second: 10, title: "Goal", actor: "A h9",
  commentary: "In!", language: "en", intensity: "peak",
};
const key = (second: number, phase: ReplayKeyframe["phase"], ball: [number, number], period = 1): ReplayKeyframe => ({
  period, match_second: second, phase, event_type: phase === "build_up" ? "pass" : "shot", player_id: "h9",
  receiver_id: null, ball, positions: [["h9", ball[0], ball[1]], ["a1", 50, 34]],
});
const story = (frames: ReplayKeyframe[]): HighlightClip => ({ ...base, playback: "story", frames });
const at = (...points: [number, number][]) => points.map(([x, y]) => ({ x, y }));
const targets = (action: [number, number][], players: [number, number][] = []): CaptionTargets =>
  ({ action: at(...action), players: at(...players) });

describe("captionPlacement", () => {
  it("moves the caption to the top when the action is along the bottom touchline, on both cameras", () => {
    const bottom = targets([[40, 62], [50, 64], [60, 66]]);
    expect(captionPlacement(bottom, "tactical", VIEW, CAPTION)).toBe("top");
    expect(captionPlacement(bottom, "broadcast", VIEW, CAPTION)).toBe("top");
  });

  it("keeps the bottom when the action is along the top touchline on the flat tactical camera", () => {
    const top = targets([[40, 2], [50, 4], [60, 6]], [[50, 60]]);
    expect(captionPlacement(top, "tactical", VIEW, CAPTION)).toBe("bottom");
  });

  it("uses the empty band above the tilted broadcast pitch when it covers fewer players than the bottom", () => {
    const top = targets([[40, 2], [50, 4], [60, 6]], [[50, 60]]);
    expect(captionPlacement(top, "broadcast", VIEW, CAPTION)).toBe("top");
  });

  it("keeps the bottom on a tie, when both bands are clear and cover the same players", () => {
    expect(captionPlacement(targets([[50, 34]]), "tactical", VIEW, CAPTION)).toBe("bottom");
  });

  it("goes compact on the side away from action spread from touchline to touchline", () => {
    const spread = targets([[20, 3], [30, 65]]);
    expect(captionPlacement(spread, "tactical", VIEW, CAPTION)).toBe("top-right");
    expect(captionPlacement(targets([[85, 3], [75, 65]]), "tactical", VIEW, CAPTION)).toBe("top-left");
  });

  it("keeps the full width above the broadcast pitch for spread action until the caption is too tall for it", () => {
    const spread = targets([[20, 3], [30, 65]]);
    expect(captionPlacement(spread, "broadcast", VIEW, CAPTION)).toBe("top");
    expect(captionPlacement(spread, "broadcast", VIEW, TALL_CAPTION)).toBe("top-right");
  });

  it("falls back to today's full-width lower third, never a compact corner, when no placement is clear", () => {
    const everywhere = targets([[2, 2], [103, 2], [2, 66], [103, 66], [52, 2], [52, 66]]);
    expect(captionPlacement(everywhere, "tactical", VIEW, CAPTION)).toBe(DEFAULT_CAPTION_PLACEMENT);
  });

  it("never picks a compact caption taller than the view, falling back to the full-width bottom", () => {
    const spread = targets([[20, 3], [30, 65]]);
    expect(captionPlacement(spread, "tactical", PHONE_VIEW, PHONE_HEIGHTS)).toBe("bottom");
    expect(captionPlacement(spread, "broadcast", PHONE_VIEW, PHONE_HEIGHTS)).toBe("bottom");
  });

  it("never picks a full-width band the caption does not fit in", () => {
    const bottom = targets([[40, 62], [50, 64], [60, 66]]);
    const tooTall = { fullPx: PHONE_VIEW.heightPx, compactPx: PHONE_VIEW.heightPx * 2 };
    expect(captionPlacement(bottom, "tactical", PHONE_VIEW, tooTall)).toBe("bottom");
  });

  it("uses a clear full-width band at phone width whichever layout was measured", () => {
    const bottom = targets([[40, 62], [50, 64], [60, 66]]);
    expect(captionPlacement(bottom, "tactical", PHONE_VIEW, PHONE_HEIGHTS)).toBe("top");
    expect(captionPlacement(bottom, "tactical", PHONE_VIEW, { heightPx: 298, compact: true })).toBe("top");
  });

  it("keeps today's lower third for the 3D camera, a clip without action, and an unmeasured view", () => {
    const bottom = targets([[50, 66]]);
    expect(captionPlacement(bottom, "3d", VIEW, CAPTION)).toBe(DEFAULT_CAPTION_PLACEMENT);
    expect(captionPlacement(targets([]), "tactical", VIEW, CAPTION)).toBe(DEFAULT_CAPTION_PLACEMENT);
    expect(captionPlacement(bottom, "tactical", { widthPx: 0, heightPx: 0 }, CAPTION)).toBe(DEFAULT_CAPTION_PLACEMENT);
    expect(DEFAULT_CAPTION_PLACEMENT).toBe("bottom");
  });
});

describe("captionRect", () => {
  it("scales an unmeasured compact height up from the full one and uses a measured compact height as is", () => {
    expect(captionRect("bottom", VIEW, CAPTION).top).toBe(VIEW.heightPx - CAPTION_INSET_Y_PX - CAPTION.heightPx);
    const estimated = captionRect("top-left", VIEW, CAPTION);
    expect(estimated.bottom - estimated.top).toBeGreaterThan(CAPTION.heightPx);
    const measured = captionRect("top-left", VIEW, { heightPx: 150, compact: true });
    expect(measured.bottom - measured.top).toBe(150);
  });

  it("uses each layout's own measured height", () => {
    const full = captionRect("top", PHONE_VIEW, PHONE_HEIGHTS);
    const compact = captionRect("top-right", PHONE_VIEW, PHONE_HEIGHTS);
    expect(full.bottom - full.top).toBe(PHONE_HEIGHTS.fullPx);
    expect(compact.bottom - compact.top).toBe(PHONE_HEIGHTS.compactPx);
  });
});

describe("layoutHeights", () => {
  it("passes measured heights through and derives the other layout from a single measurement", () => {
    expect(layoutHeights(PHONE_HEIGHTS, PHONE_VIEW)).toEqual(PHONE_HEIGHTS);
    const fromCompact = layoutHeights({ heightPx: 300, compact: true }, VIEW);
    expect(fromCompact.compactPx).toBe(300);
    expect(fromCompact.fullPx).toBeLessThan(300);
    const fromFull = layoutHeights(CAPTION, VIEW);
    expect(fromFull.fullPx).toBe(CAPTION.heightPx);
    expect(fromFull.compactPx).toBeGreaterThan(CAPTION.heightPx);
  });
});

describe("storyTargets", () => {
  const frames = [key(10, "build_up", [90, 60], 2), key(14, "shot", [95, 40], 2), key(14.4, "flight", [105, 34], 2)];

  it("lists every keyframe ball in the screen frame (mirrored in the second half) and the actor at every tick", () => {
    const clip = story(frames);
    const ticks = Math.ceil(reelClipLengthMs(clip) / TICK);
    const { action, players } = storyTargets(clip, TICK);
    expect(action.slice(0, 3)).toEqual(at([15, 8], [10, 28], [0, 34]));
    expect(action).toHaveLength(3 + ticks);
    expect(action[3]).toEqual({ x: 15, y: 8 });
    expect(players).toHaveLength(2 * ticks);
  });

  it("returns no targets for a frame clip, which keeps today's layout", () => {
    const clip: HighlightClip = { ...base, playback: "frames", frames };
    expect(storyTargets(clip, TICK)).toEqual({ action: [], players: [] });
  });
});
