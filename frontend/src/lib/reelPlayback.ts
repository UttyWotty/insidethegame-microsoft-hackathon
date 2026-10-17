/**
 * Pure choice of how a highlights clip plays: shot clips replay their story, other clips replay the passes and
 * carries around the moment, and clips with neither step through stored frames. Story clips use the instant
 * replay's timeline (build-up at real pace, the strike in slow motion, interpolated between keyframes) followed by
 * the reel's caption hold; frame clips keep the reel's real-pace frame stepping.
 * Every view is returned in the screen frame, mirrored for the second half, so the player only draws it.
 */
import type { HighlightClip, Point } from "../types";
import { toScreen } from "./pitch";
import { CLIP_HOLD_MS, clipLengthMs, frameBall, frameIndexAt, framePositions, glideMs } from "./reel";
import { clockAt, motionMs, sampleAt } from "./replayTimeline";

/** What the reel shows at one instant, in the screen frame, with the players to tag and the glide time. */
export interface ReelView {
  ball: Point; positions: Record<string, Point>; actor: string | null; receiver: string | null; moveMs: number;
}

/** Real milliseconds a clip occupies: a story's motion plus CLIP_HOLD_MS, or the frame clip's length. */
export function reelClipLengthMs(clip: HighlightClip): number {
  return clip.playback === "story" ? motionMs(clip.frames) + CLIP_HOLD_MS : clipLengthMs(clip);
}

/**
 * The view of a clip after elapsedMs, or null when it has no frames. Story clips are sampled continuously, so the
 * dots move over one tick (tickMs); frame clips glide to the next stored frame over the gap between them.
 */
export function reelView(clip: HighlightClip, elapsedMs: number, tickMs: number): ReelView | null {
  if (!clip.frames.length) return null;
  if (clip.playback === "story") {
    const frames = clip.frames;
    const sample = sampleAt(frames, clockAt(frames, elapsedMs));
    const period = frames[sample.index].period;
    const positions = Object.fromEntries(sample.positions.map(([id, x, y]) => [id, toScreen({ x, y }, true, period)]));
    return {
      ball: toScreen(sample.ball, true, period), positions, actor: sample.actor,
      receiver: frames[sample.index].receiver_id, moveMs: tickMs,
    };
  }
  const index = frameIndexAt(clip, elapsedMs);
  const frame = clip.frames[index];
  return {
    ball: frameBall(frame), positions: framePositions(frame), actor: frame.player_id, receiver: null,
    moveMs: glideMs(clip, index),
  };
}
