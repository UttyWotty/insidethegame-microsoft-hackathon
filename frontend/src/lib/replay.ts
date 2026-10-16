/**
 * Pure rules for instant replays: which shots earn one, which goal the replay camera sits behind, how the 2D
 * replay zooms in on the action, and what the commentator says as the replay rolls.
 */
import type { ShotTrace } from "../state/matchState";
import type { HighlightFrame, Point } from "../types";
import { PITCH_LENGTH, PITCH_WIDTH } from "./pitch";
import { frameBall } from "./reel";

/** Shots with at least this xG get a replay even when they miss; matches the server's big-chance threshold. */
export const REPLAY_MIN_XG = 0.25;
/** Speech speed passed to the commentator's line as a replay rolls, matching the slower replay mood. */
export const REPLAY_SPEECH_RATE = 0.6;
/** Wait after the shot before the replay rolls, so the live reaction and goal banner are seen first. */
export const REPLAY_DELAY_MS = 3500;
/** Size of the 2D replay window in metres, a zoomed TV-style crop. */
export const ZOOM_LENGTH = 52;
export const ZOOM_WIDTH = 34;
const HALFWAY = PITCH_LENGTH / 2;
const GOAL_LINES = ["Let's see that again.", "Here it is once more.", "Watch this again.", "One more look at that."];
const MISS_LINES = ["Let's have another look.", "How did that stay out?", "Take another look at this chance."];

export type GoalEnd = "left" | "right";

/** Whether a shot earns an instant replay: every goal, and misses or saves of big chances. */
export function earnsReplay(shot: ShotTrace): boolean {
  return shot.result === "goal" || (shot.xg ?? 0) >= REPLAY_MIN_XG;
}

/** The goal the action finished at, from where the ball ends up: the replay camera sits behind it. */
export function goalEnd(frames: HighlightFrame[]): GoalEnd {
  const last = frames[frames.length - 1];
  return last && frameBall(last).x < HALFWAY ? "left" : "right";
}

/** A zoomed 2D window centred on the action, kept inside the pitch: x, y, width, height in metres. */
export function zoomBox(centre: Point): [number, number, number, number] {
  const x = Math.min(Math.max(centre.x - ZOOM_LENGTH / 2, 0), PITCH_LENGTH - ZOOM_LENGTH);
  const y = Math.min(Math.max(centre.y - ZOOM_WIDTH / 2, 0), PITCH_WIDTH - ZOOM_WIDTH);
  return [x, y, ZOOM_LENGTH, ZOOM_WIDTH];
}

/** The commentator's line as a replay rolls, rotated by the shot id so repeats vary. */
export function replayLine(shot: ShotTrace): string {
  const lines = shot.result === "goal" ? GOAL_LINES : MISS_LINES;
  const index = [...shot.id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % lines.length;
  return lines[index];
}
