/**
 * Pure maths for the 3D broadcast view: pitch to world coordinates, a TV camera that follows the ball along the
 * touchline, smooth approach of the camera, and time-based interpolation of player and ball movement.
 * The world is centred on the centre spot with x along the pitch, y up, and z toward the main camera.
 */
import type { Point } from "../types";
import { PITCH_LENGTH, PITCH_WIDTH } from "./pitch";

/** A point in world space. */
export interface Vec3 { x: number; y: number; z: number }

/** Main camera height and distance from the centre line toward the near touchline, in metres. */
export const CAMERA_HEIGHT = 36;
export const CAMERA_DEPTH = 66;
/** How far the camera may pan along the touchline either side of halfway. */
export const CAMERA_PAN_LIMIT = 28;
/** The camera aims at the middle of the pitch's width, shifted slightly toward the ball. */
const LOOK_OFFSET_Z = 3;
/** Fraction of the ball's offset across the pitch the camera aim follows. */
const LOOK_FOLLOW_Z = 0.2;
/** Time for the camera to cover half the remaining distance to its target. */
export const CAMERA_HALF_LIFE_MS = 450;

/** Pitch metres (x along, y across with 0 at the far touchline) to world coordinates on the grass. */
export function pitchToWorld(point: Point, height = 0): Vec3 {
  return { x: point.x - PITCH_LENGTH / 2, y: height, z: point.y - PITCH_WIDTH / 2 };
}

/** Camera position and aim for a ball position: pans along the touchline to keep the ball in the middle. */
export function broadcastCamera(ball: Point | null): { position: Vec3; target: Vec3 } {
  const world = pitchToWorld(ball ?? { x: PITCH_LENGTH / 2, y: PITCH_WIDTH / 2 });
  const panX = Math.min(Math.max(world.x, -CAMERA_PAN_LIMIT), CAMERA_PAN_LIMIT);
  return {
    position: { x: panX, y: CAMERA_HEIGHT, z: CAMERA_DEPTH },
    target: { x: panX, y: 0, z: world.z * LOOK_FOLLOW_Z + LOOK_OFFSET_Z },
  };
}

/** Exponential approach of current toward target after elapsedMs with the given half-life. */
export function approach(current: number, target: number, elapsedMs: number, halfLifeMs: number): number {
  const keep = Math.pow(0.5, Math.max(elapsedMs, 0) / Math.max(halfLifeMs, 1));
  return target + (current - target) * keep;
}

/** A movement from one pitch point to another over a duration starting at a time. */
export interface Glide { from: Point; to: Point; startedAt: number; durationMs: number }

/** Where a glide is at time now: linear between its ends, holding at the destination once complete. */
export function glideAt(glide: Glide, now: number): Point {
  const t = glide.durationMs <= 0 ? 1 : Math.min(Math.max((now - glide.startedAt) / glide.durationMs, 0), 1);
  return { x: glide.from.x + (glide.to.x - glide.from.x) * t, y: glide.from.y + (glide.to.y - glide.from.y) * t };
}

/** Facing angle (radians about the vertical) for movement from one pitch point to another, or null if still. */
export function heading(from: Point, to: Point): number | null {
  const dx = to.x - from.x;
  const dz = to.y - from.y;
  return Math.hypot(dx, dz) < 0.05 ? null : Math.atan2(dx, dz);
}

/** Like approach, for angles in radians: turns the short way round. */
export function approachAngle(current: number, target: number, elapsedMs: number, halfLifeMs: number): number {
  const delta = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return approach(current, current + delta, elapsedMs, halfLifeMs);
}

/** Leg swing angle (radians) for a running phase; zero when standing. */
export const STRIDE_ANGLE = 0.6;
export function legSwing(phase: number, moving: boolean): number {
  return moving ? Math.sin(phase) * STRIDE_ANGLE : 0;
}
