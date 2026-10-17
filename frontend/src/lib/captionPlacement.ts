/**
 * Pure placement of the highlights caption so it never covers a story clip's action: the keyframe ball positions
 * and the acting player's dot at every playback tick, projected through the camera into the pitch view.
 * Only placements that fit inside the view are eligible: the full-width caption goes to whichever band is clear of
 * the action and covers fewer players, then a compact caption on the side away from the action. When nothing
 * eligible is clear, and for frame clips and the 3D camera, it keeps today's full-width lower third.
 */
import type { HighlightClip, Point } from "../types";
import { toScreen } from "./pitch";
import { reelClipLengthMs, reelView } from "./reelPlayback";
import { type FlatCamera, projectToView, type ViewSize } from "./viewProjection";

export type CaptionCamera = FlatCamera | "3d";
export type CaptionPlacement = "bottom" | "top" | "top-left" | "top-right" | "bottom-left" | "bottom-right";

/** Today's lower third: kept for frame clips, the 3D camera, and before the view is measured. */
export const DEFAULT_CAPTION_PLACEMENT: CaptionPlacement = "bottom";
/** Mirrors `.highlight-caption` in app.css: left and right insets var(--space-5), top or bottom var(--space-4). */
export const CAPTION_INSET_X_PX = 24;
export const CAPTION_INSET_Y_PX = 16;
/** Mirrors `.highlight-caption.compact { width: 40% }` in app.css, as a fraction of the view width. */
export const COMPACT_WIDTH_FRACTION = 0.4;
/** Metres kept clear around every ball and player position: the dot's radius (1.5 m) plus its outline. */
export const MARKER_CLEARANCE_M = 2;
/** Pixels of grass kept between the caption and any marker. */
export const CAPTION_GAP_PX = 4;
const HALF = 2;

/** One measurement of the caption: its height in pixels and whether it was laid out compact at the time. */
export interface CaptionBox { heightPx: number; compact: boolean }

/** Both layouts measured on their own: the full-width height and the compact height, in pixels. */
export interface CaptionHeights { fullPx: number; compactPx: number }

/** What the rule accepts: both layouts measured, or one measurement from which the other layout is derived. */
export type CaptionMeasure = CaptionBox | CaptionHeights;

/** Screen positions the caption must not cover (action) and, among clear placements, should cover least (players). */
export interface CaptionTargets { action: Point[]; players: Point[] }

interface Rect { left: number; top: number; right: number; bottom: number }

/** Whether a placement is a compact, side-anchored caption rather than the full-width lower third. */
export function isCompact(placement: CaptionPlacement): boolean {
  return placement !== "top" && placement !== "bottom";
}

/**
 * What a story clip's caption must avoid (action: every keyframe ball and the acting player at every tickMs of
 * playback, the ticks the reel player draws) and should avoid (players: every player at those ticks), in the
 * screen frame. Frame clips return neither, so they keep today's layout.
 */
export function storyTargets(clip: HighlightClip, tickMs: number): CaptionTargets {
  if (clip.playback !== "story") return { action: [], players: [] };
  const action = clip.frames.map((f) => toScreen({ x: f.ball[0], y: f.ball[1] }, true, f.period));
  const players: Point[] = [];
  const length = reelClipLengthMs(clip);
  for (let elapsed = 0; elapsed < length; elapsed += tickMs) {
    const view = reelView(clip, elapsed, tickMs);
    if (!view) continue;
    const actor = view.actor ? view.positions[view.actor] : undefined;
    if (actor) action.push(actor);
    players.push(...Object.values(view.positions));
  }
  return { action, players };
}

/** The pixel box a marker at a point can cover: its clearance square projected into the view. */
function markerRect(point: Point, camera: FlatCamera, view: ViewSize): Rect {
  const corners = [-1, 1].flatMap((sx) => [-1, 1].map((sy) => projectToView(
    { x: point.x + sx * MARKER_CLEARANCE_M, y: point.y + sy * MARKER_CLEARANCE_M }, camera, view)));
  const xs = corners.map((c) => c.x);
  const ys = corners.map((c) => c.y);
  return { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) };
}

/**
 * The height of each layout. Measured heights are used as they are; from a single measurement the other layout's
 * height is derived by scaling with the width ratio, so one layout's height never stands in for the other's.
 */
export function layoutHeights(caption: CaptionMeasure, view: ViewSize): CaptionHeights {
  if ("fullPx" in caption) return caption;
  const ratio = (view.widthPx - HALF * CAPTION_INSET_X_PX) / (COMPACT_WIDTH_FRACTION * view.widthPx);
  return caption.compact
    ? { fullPx: caption.heightPx / ratio, compactPx: caption.heightPx }
    : { fullPx: caption.heightPx, compactPx: caption.heightPx * ratio };
}

/** The caption's pixel box for a placement, using the height of that placement's own layout. */
export function captionRect(placement: CaptionPlacement, view: ViewSize, caption: CaptionMeasure): Rect {
  const compactWidth = COMPACT_WIDTH_FRACTION * view.widthPx;
  const compact = isCompact(placement);
  const heights = layoutHeights(caption, view);
  const height = compact ? heights.compactPx : heights.fullPx;
  const atTop = placement.startsWith("top");
  const top = atTop ? CAPTION_INSET_Y_PX : view.heightPx - CAPTION_INSET_Y_PX - height;
  const left = placement.endsWith("right") ? view.widthPx - CAPTION_INSET_X_PX - compactWidth : CAPTION_INSET_X_PX;
  const right = compact ? left + compactWidth : view.widthPx - CAPTION_INSET_X_PX;
  return { left, top, right, bottom: top + height };
}

/** Whether a caption box lies fully inside the view, so no part of it is cut off by the pitch frame. */
function fitsView(box: Rect, view: ViewSize): boolean {
  return box.left >= 0 && box.top >= 0 && box.right <= view.widthPx && box.bottom <= view.heightPx;
}

function overlaps(a: Rect, b: Rect): boolean {
  return a.left < b.right + CAPTION_GAP_PX && b.left < a.right + CAPTION_GAP_PX
    && a.top < b.bottom + CAPTION_GAP_PX && b.top < a.bottom + CAPTION_GAP_PX;
}

/** Candidates in tiers: the full-width lower third (bottom, then top), then compact corners, away side first. */
function tiers(action: Rect[], view: ViewSize): CaptionPlacement[][] {
  const centre = action.reduce((sum, m) => sum + (m.left + m.right) / HALF, 0) / action.length;
  const [away, near] = centre < view.widthPx / HALF ? ["right", "left"] : ["left", "right"];
  return [["bottom", "top"], [`top-${away}`, `bottom-${away}`, `top-${near}`, `bottom-${near}`] as CaptionPlacement[]];
}

/** The candidate with the fewest hits by score, the earliest on a tie. */
function fewest(candidates: CaptionPlacement[], score: (placement: CaptionPlacement) => number): CaptionPlacement {
  return candidates.reduce((best, next) => (score(next) < score(best) ? next : best));
}

/**
 * Where the caption goes for a clip's targets under a camera, in a view of a measured size. A placement is eligible
 * only if its box fits inside the view. Within the first tier that has eligible placements clear of every action
 * marker, the one covering the fewest player markers wins (bottom on a tie), so a compact caption is used only when
 * neither full-width band is. When no eligible placement is clear, the caption keeps DEFAULT_CAPTION_PLACEMENT,
 * today's full-width lower third, so it is never worse than before. The 3D camera, a clip without action, and an
 * unmeasured view keep DEFAULT_CAPTION_PLACEMENT too.
 */
export function captionPlacement(targets: CaptionTargets, camera: CaptionCamera, view: ViewSize,
                                 caption: CaptionMeasure): CaptionPlacement {
  if (camera === "3d" || !targets.action.length || view.widthPx <= 0 || view.heightPx <= 0) {
    return DEFAULT_CAPTION_PLACEMENT;
  }
  const heights = layoutHeights(caption, view);
  if (heights.fullPx <= 0 || heights.compactPx <= 0) return DEFAULT_CAPTION_PLACEMENT;
  const action = targets.action.map((p) => markerRect(p, camera, view));
  const players = targets.players.map((p) => markerRect(p, camera, view));
  const hits = (markers: Rect[]) => (placement: CaptionPlacement): number => {
    const box = captionRect(placement, view, heights);
    return markers.filter((m) => overlaps(box, m)).length;
  };
  const eligible = (placement: CaptionPlacement): boolean => fitsView(captionRect(placement, view, heights), view);
  for (const tier of tiers(action, view)) {
    const clear = tier.filter((placement) => eligible(placement) && hits(action)(placement) === 0);
    if (clear.length) return fewest(clear, hits(players));
  }
  return DEFAULT_CAPTION_PLACEMENT;
}
