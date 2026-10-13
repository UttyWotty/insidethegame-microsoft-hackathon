/**
 * Pure timing for on-pitch player motion and sprint tags.
 * Players glide between tracking frames over the real time between events, so movement looks continuous at any
 * replay speed, and a sprint tag stays on the sprinting player briefly after the frame that reported it.
 */
import type { SprintTag } from "../types";

/** Glide time used for the first frame of a match, before any gap between events is known. */
export const DEFAULT_MOVE_MS = 650;
/** Shortest glide, so back-to-back events still animate instead of snapping. */
export const MIN_MOVE_MS = 150;
/** Longest glide, so a long stoppage does not leave players drifting for seconds. */
export const MAX_MOVE_MS = 1500;
/** How long a sprint tag stays on screen after the frame that reported it. */
export const SPRINT_TAG_MS = 1800;

/** A sprint tag stamped with the wall-clock time it arrived. */
export interface ReceivedSprint extends SprintTag { at: number }

/** Glide time for the next frame: the real gap since the previous event (null at kick-off), within bounds. */
export function moveDuration(previousAt: number | null, at: number): number {
  if (previousAt === null) return DEFAULT_MOVE_MS;
  return Math.min(Math.max(at - previousAt, MIN_MOVE_MS), MAX_MOVE_MS);
}

/** Speed to show on a player now, or null when they are not the recent sprinter. */
export function sprintSpeed(sprint: ReceivedSprint | null, playerId: string, now: number): number | null {
  if (!sprint || sprint.player_id !== playerId || now - sprint.at > SPRINT_TAG_MS) return null;
  return sprint.speed_kmh;
}
