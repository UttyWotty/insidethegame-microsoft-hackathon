/**
 * Pure playback timing for replayed frames: highlights clips at real match pace and instant replays in slow motion.
 * The frame shown is the last one at or before the elapsed time, players glide to the next frame over the gap
 * between them (scaled by the playback rate), and each clip holds briefly on its final frame.
 */
import type { HighlightFrame, Point } from "../types";
import { MAX_MOVE_MS, MIN_MOVE_MS } from "./motion";
import { toScreen } from "./pitch";

/** Match seconds per real second while a clip plays. */
export const REEL_RATE = 1;
/** Pause on a clip's last frame so its caption and narration can finish. */
export const CLIP_HOLD_MS = 2500;
const MS_PER_SECOND = 1000;

/** Anything with stored frames to play: a highlights clip or an instant replay. */
export interface Playable { frames: HighlightFrame[] }

/** Real milliseconds a clip occupies at a playback rate (default REEL_RATE), including the hold on its last frame. */
export function clipLengthMs(clip: Playable, rate: number = REEL_RATE): number {
  const frames = clip.frames;
  const span = frames.length ? frames[frames.length - 1].match_second - frames[0].match_second : 0;
  return (span / rate) * MS_PER_SECOND + CLIP_HOLD_MS;
}

/** Index of the frame to show after elapsedMs of a clip at a playback rate (default REEL_RATE). */
export function frameIndexAt(clip: Playable, elapsedMs: number, rate: number = REEL_RATE): number {
  const frames = clip.frames;
  if (!frames.length) return 0;
  const clock = frames[0].match_second + (elapsedMs / MS_PER_SECOND) * rate;
  let index = 0;
  while (index + 1 < frames.length && frames[index + 1].match_second <= clock) index += 1;
  return index;
}

/**
 * Glide time toward the frame after index from the match time between them at a playback rate, within bounds.
 * Defaults: rate REEL_RATE and maxMs MAX_MOVE_MS (slow-motion replays pass a longer maximum).
 */
export function glideMs(clip: Playable, index: number, rate: number = REEL_RATE, maxMs: number = MAX_MOVE_MS): number {
  const current = clip.frames[index];
  const next = clip.frames[index + 1];
  if (!current || !next) return MIN_MOVE_MS;
  const gap = ((next.match_second - current.match_second) / rate) * MS_PER_SECOND;
  return Math.min(Math.max(gap, MIN_MOVE_MS), maxMs);
}

/** Screen positions of all players in a frame (stored in the absolute home frame). */
export function framePositions(frame: HighlightFrame): Record<string, Point> {
  return Object.fromEntries(frame.positions.map(([id, x, y]) => [id, toScreen({ x, y }, true, frame.period)]));
}

/** Screen position of the ball in a frame. */
export function frameBall(frame: HighlightFrame): Point {
  return toScreen({ x: frame.ball[0], y: frame.ball[1] }, true, frame.period);
}
