/**
 * Pure projection of a pitch point (metres, screen frame) to pixels in the 2D pitch view for a camera.
 * The tactical camera draws the SVG pitch flat; the broadcast camera tilts it with the CSS 3D transform in app.css
 * (rotateX and scale about the transform origin, seen through the wrapper's perspective), mirrored here exactly.
 * The 3D camera is drawn by three.js and has no projection here.
 */
import type { Point } from "../types";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M, RUNOFF_TOP_M } from "./pitch";

/** The 2D cameras whose projection is known: the flat tactical view and the tilted broadcast view. */
export type FlatCamera = "broadcast" | "tactical";

/** Size of the pitch view (the overlay layer over the SVG) in CSS pixels. */
export interface ViewSize { widthPx: number; heightPx: number }

/** Mirrors `.pitch-wrap.cam-broadcast .pitch { transform: rotateX(30deg) scale(0.86) }` in app.css. */
export const BROADCAST_TILT_DEG = 30;
export const BROADCAST_SCALE = 0.86;
/** Mirrors `.pitch-wrap { perspective: 1400px }` in app.css. */
export const PERSPECTIVE_PX = 1400;
/** Mirrors `transform-origin: 50% 55%` of the pitch SVG in app.css, as fractions of its box. */
const ORIGIN_X = 0.5;
const ORIGIN_Y = 0.55;
/** The default perspective-origin (50% 50%) of the pitch wrapper, as fractions of its box. */
const PERSPECTIVE_ORIGIN = 0.5;
/** The SVG viewBox the pitch draws (pitch plus runoff), in metres. */
const VIEW_X = -RUNOFF_M;
const VIEW_Y = -RUNOFF_TOP_M;
const VIEW_LENGTH = PITCH_LENGTH + 2 * RUNOFF_M;
const VIEW_HEIGHT = PITCH_WIDTH + RUNOFF_TOP_M + RUNOFF_M;
const DEG_TO_RAD = Math.PI / 180;

/** A point's position in the flat SVG, in pixels from the view's top-left corner. */
function flatPx(point: Point, view: ViewSize): Point {
  const svgHeight = (view.widthPx * VIEW_HEIGHT) / VIEW_LENGTH;
  return { x: ((point.x - VIEW_X) / VIEW_LENGTH) * view.widthPx, y: ((point.y - VIEW_Y) / VIEW_HEIGHT) * svgHeight };
}

/** Where a flat SVG pixel lands after the broadcast tilt and the wrapper's perspective. */
function tiltPx(flat: Point, view: ViewSize): Point {
  const svgHeight = (view.widthPx * VIEW_HEIGHT) / VIEW_LENGTH;
  const originX = ORIGIN_X * view.widthPx;
  const originY = ORIGIN_Y * svgHeight;
  const angle = BROADCAST_TILT_DEG * DEG_TO_RAD;
  const dx = (flat.x - originX) * BROADCAST_SCALE;
  const dy = (flat.y - originY) * BROADCAST_SCALE;
  const x = originX + dx;
  const y = originY + dy * Math.cos(angle);
  const z = dy * Math.sin(angle);
  const factor = PERSPECTIVE_PX / (PERSPECTIVE_PX - z);
  const eyeX = PERSPECTIVE_ORIGIN * view.widthPx;
  const eyeY = PERSPECTIVE_ORIGIN * view.heightPx;
  return { x: eyeX + (x - eyeX) * factor, y: eyeY + (y - eyeY) * factor };
}

/** The pixel position in the view of a pitch point (metres, screen frame) under a 2D camera. */
export function projectToView(point: Point, camera: FlatCamera, view: ViewSize): Point {
  const flat = flatPx(point, view);
  return camera === "broadcast" ? tiltPx(flat, view) : flat;
}
