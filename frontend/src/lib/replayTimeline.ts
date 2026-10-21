/**
 * Pure playback of an instant replay story: build-up keyframes at real match pace, the strike in slow motion, then
 * a hold on the analysis card. The match clock is derived from elapsed real time segment by segment.
 * The ball and players are interpolated linearly between the surrounding keyframes in the absolute home frame.
 */
import type { Point, ReplayKeyframe, TrackingFrame } from "../types";

/** Match seconds per real second while the build-up plays: real pace. */
export const REPLAY_BUILDUP_RATE = 1;
/** Match seconds per real second from the strike to the ball's arrival: slow motion. */
export const REPLAY_FLIGHT_RATE = 0.25;
/** Real milliseconds the analysis card holds after the ball arrives. */
export const REPLAY_ANALYSIS_HOLD_MS = 5000;
const MS_PER_SECOND = 1000;

/** What the replay shows at one instant: ball and players (absolute frame), the keyframe index, and its actor. */
export interface ReplaySample { ball: Point; positions: TrackingFrame; index: number; actor: string | null }

export type ReplayStage = "build_up" | "shot" | "analysis";

/** Playback rate of the segment that starts at a keyframe: slow motion after the strike, real pace otherwise. */
export function segmentRate(from: ReplayKeyframe): number {
  return from.phase === "shot" ? REPLAY_FLIGHT_RATE : REPLAY_BUILDUP_RATE;
}

function segmentMs(from: ReplayKeyframe, to: ReplayKeyframe): number {
  return (Math.max(to.match_second - from.match_second, 0) / segmentRate(from)) * MS_PER_SECOND;
}

/** Real milliseconds of motion from the first keyframe to the last. */
export function motionMs(frames: ReplayKeyframe[]): number {
  let total = 0;
  for (let i = 0; i + 1 < frames.length; i += 1) total += segmentMs(frames[i], frames[i + 1]);
  return total;
}

/** Real milliseconds of the whole replay: motion plus the analysis hold. */
export function replayLengthMs(frames: ReplayKeyframe[]): number {
  return motionMs(frames) + REPLAY_ANALYSIS_HOLD_MS;
}

/** The match second shown after elapsedMs of playback, clamped to the last keyframe (0 without keyframes). */
export function clockAt(frames: ReplayKeyframe[], elapsedMs: number): number {
  if (!frames.length) return 0;
  let remaining = Math.max(elapsedMs, 0);
  for (let i = 0; i + 1 < frames.length; i += 1) {
    const span = segmentMs(frames[i], frames[i + 1]);
    if (remaining < span) return frames[i].match_second + (remaining / MS_PER_SECOND) * segmentRate(frames[i]);
    remaining -= span;
  }
  return frames[frames.length - 1].match_second;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function blendPositions(from: TrackingFrame, to: TrackingFrame, t: number): TrackingFrame {
  const target = new Map(to.map(([id, x, y]) => [id, [x, y] as const]));
  const blended: TrackingFrame = from.map(([id, x, y]) => {
    const end = target.get(id);
    return end ? [id, lerp(x, end[0], t), lerp(y, end[1], t)] : [id, x, y];
  });
  const seen = new Set(from.map(([id]) => id));
  return blended.concat(to.filter(([id]) => !seen.has(id)));
}

/** Index of the last keyframe at or before clock (0 when clock precedes them all). */
function indexAt(frames: ReplayKeyframe[], clock: number): number {
  let index = 0;
  while (index + 1 < frames.length && frames[index + 1].match_second <= clock) index += 1;
  return index;
}

/**
 * Ball and players at a match second, interpolated between the surrounding keyframes. A player missing from one
 * of the two keyframes keeps the position from the one that has them. Requires at least one keyframe.
 */
export function sampleAt(frames: ReplayKeyframe[], clock: number): ReplaySample {
  const index = indexAt(frames, clock);
  const from = frames[index];
  const to = frames[index + 1];
  const span = to ? to.match_second - from.match_second : 0;
  const t = to && span > 0 ? Math.min(Math.max((clock - from.match_second) / span, 0), 1) : 0;
  const end = to ?? from;
  return {
    ball: { x: lerp(from.ball[0], end.ball[0], t), y: lerp(from.ball[1], end.ball[1], t) },
    positions: blendPositions(from.positions, end.positions, t), index, actor: from.player_id,
  };
}

/** Which part of the replay is on screen: the build-up, the strike and flight, or the analysis hold. */
export function replayStage(frames: ReplayKeyframe[], elapsedMs: number): ReplayStage {
  if (elapsedMs >= motionMs(frames)) return "analysis";
  const shot = frames.find((f) => f.phase === "shot");
  return shot && clockAt(frames, elapsedMs) >= shot.match_second ? "shot" : "build_up";
}
