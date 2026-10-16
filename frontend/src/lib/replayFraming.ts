/**
 * Pure framing for the 2D instant replay: a crop that contains the whole replayed action, and the card's side.
 * The crop holds every build-up ball point, the shot origin, the goal mouth, and the ball's final position with a
 * margin, keeps the zoomed crop's aspect, and puts the shot cone in the half nearest the attacked goal.
 * The analysis card then sits on the other half, so it never covers the cone, goal mouth, shooter, or final ball.
 */
import type { Point } from "../types";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M, RUNOFF_TOP_M } from "./pitch";
import { type GoalEnd, ZOOM_LENGTH, ZOOM_WIDTH, zoomBox } from "./replay";

/** Metres of clear grass kept around every framed point, so a ball on the goal line is drawn whole. */
export const REPLAY_MARGIN_M = 3;
/** Width over height of every replay crop: the zoomed crop's shape, so the view never changes aspect. */
const ASPECT = ZOOM_LENGTH / ZOOM_WIDTH;
/** The drawn area (pitch plus runoff) the crop is clamped to, as x, y, width, height in metres. */
const AREA_X = -RUNOFF_M;
const AREA_Y = -RUNOFF_TOP_M;
const AREA_LENGTH = PITCH_LENGTH + 2 * RUNOFF_M;
const AREA_HEIGHT = PITCH_WIDTH + RUNOFF_TOP_M + RUNOFF_M;
const HALF = 2;

export type Crop = [number, number, number, number];
export type CardSide = "left" | "right";

interface Bounds { x0: number; x1: number; y0: number; y1: number }

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

/** The bounding box of the points, grown by REPLAY_MARGIN_M on every side. */
function padded(points: Point[]): Bounds {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  return { x0: Math.min(...xs) - REPLAY_MARGIN_M, x1: Math.max(...xs) + REPLAY_MARGIN_M,
    y0: Math.min(...ys) - REPLAY_MARGIN_M, y1: Math.max(...ys) + REPLAY_MARGIN_M };
}

/** Whether every cone point, with its margin, lies in the crop's half nearest the attacked goal. */
function coneInGoalHalf(crop: Crop, cone: Point[], goal: GoalEnd): boolean {
  const middle = crop[0] + crop[2] / HALF;
  return cone.every((p) => (goal === "left" ? p.x + REPLAY_MARGIN_M <= middle : p.x - REPLAY_MARGIN_M >= middle));
}

function fits(crop: Crop, box: Bounds, cone: Point[], goal: GoalEnd): boolean {
  const [x, y, w, h] = crop;
  return box.x0 >= x && box.x1 <= x + w && box.y0 >= y && box.y1 <= y + h && coneInGoalHalf(crop, cone, goal);
}

/** The cone's furthest reach from the goal-side edge of the box, doubled: the width that keeps it in the goal half. */
function goalHalfWidth(box: Bounds, cone: Point[], goal: GoalEnd): number {
  const reach = cone.map((p) => (goal === "left" ? p.x + REPLAY_MARGIN_M - box.x0 : box.x1 - (p.x - REPLAY_MARGIN_M)));
  return HALF * Math.max(0, ...reach);
}

/**
 * The 2D replay crop (x, y, width, height in metres, screen frame) for the action points and the cone points.
 * action lists every point that must be visible (build-up ball points, shot origin, goal posts, final ball); cone
 * lists those that must sit in the half nearest the attacked goal (shot origin, posts, final ball). The zoomed crop
 * centred on the action is kept when it already fits; otherwise the crop grows from the zoomed size, keeping its
 * aspect, is anchored at the goal-side edge of the action, and is clamped to the drawn pitch and runoff.
 */
export function replayCrop(action: Point[], cone: Point[], goal: GoalEnd): Crop {
  if (!action.length) return zoomBox({ x: PITCH_LENGTH / HALF, y: PITCH_WIDTH / HALF });
  const box = padded(action);
  const base = zoomBox({ x: (box.x0 + box.x1) / HALF, y: (box.y0 + box.y1) / HALF });
  if (fits(base, box, cone, goal)) return base;
  const wanted = Math.max(ZOOM_LENGTH, box.x1 - box.x0, (box.y1 - box.y0) * ASPECT, goalHalfWidth(box, cone, goal));
  const width = Math.min(wanted, AREA_LENGTH, AREA_HEIGHT * ASPECT);
  const height = width / ASPECT;
  const left = goal === "left" ? box.x0 : box.x1 - width;
  const top = (box.y0 + box.y1 - height) / HALF;
  return [clamp(left, AREA_X, AREA_X + AREA_LENGTH - width), clamp(top, AREA_Y, AREA_Y + AREA_HEIGHT - height),
    width, height];
}

/** The side of the view the analysis card sits on: the half away from the attacked goal. */
export function cardSide(goal: GoalEnd): CardSide {
  return goal === "left" ? "right" : "left";
}
