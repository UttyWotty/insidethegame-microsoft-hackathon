/**
 * Automated highlights reel: shot clips replay the real build-up and the ball's flight, other clips stored frames.
 * Build-up plays at real match pace and the strike in slow motion, a broadcast caption that keeps clear of the
 * clip's action captions it, and the commentator narrates it when Voice is on. Viewers can pause, skip between clips, replay, or go back to live.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { isCompact } from "../lib/captionPlacement";
import { playerDots } from "../lib/playerDots";
import { REEL_RATE } from "../lib/reel";
import { reelClipLengthMs, reelView } from "../lib/reelPlayback";
import { speakLine, stopSpeaking } from "../lib/speakLine";
import { COMPACT_CLASS, MEASURE_CLASS, useCaptionPlacement } from "../lib/useCaptionPlacement";
import type { HighlightClip, HighlightReel, MatchMetadata } from "../types";
import { type BallAnchor } from "./Pitch";
import { PitchView, type Camera } from "./PitchView";

const TICK_MS = 100;
const NO_SPRINT = () => null;

/** The caption's lines; shared by the visible caption and the hidden twins measured for placement. */
function CaptionBody({ label, position, count, clip }: { label: string; position: number; count: number;
                                                      clip: HighlightClip }) {
  return (
    <>
      <span className="term">{label} - {position} of {count}</span>
      <strong className="display highlight-title">{clip.minute} {clip.title}{clip.actor ? ` - ${clip.actor}` : ""}</strong>
      <span>{clip.commentary}</span>
    </>
  );
}

interface HighlightsPlayerProps {
  sessionId: string; stage: HighlightReel["stage"]; segment?: string; match: MatchMetadata;
  homeColor: string; awayColor: string; camera: Camera; voiceOn: boolean; onClose: () => void;
}

export function HighlightsPlayer(props: HighlightsPlayerProps) {
  const { sessionId, stage, segment, match, homeColor, awayColor, camera, voiceOn, onClose } = props;
  const [reel, setReel] = useState<HighlightReel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clipIndex, setClipIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const onBallAnchor = useCallback((_: BallAnchor) => undefined, []);
  const spoken = useRef<string | null>(null);

  useEffect(() => {
    api.highlights(sessionId, stage, segment).then(setReel)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Highlights unavailable"));
    return stopSpeaking;
  }, [sessionId, stage, segment]);

  const clips = reel?.clips ?? [];
  const clip = clips[clipIndex];
  const finished = reel !== null && clipIndex >= clips.length;
  const { fullRef, compactRef, placement } = useCaptionPlacement(clip ?? null, camera, TICK_MS);
  const compact = isCompact(placement);

  useEffect(() => {
    if (!clip || paused) return undefined;
    const id = window.setInterval(() => setElapsed((ms) => ms + TICK_MS), TICK_MS);
    return () => window.clearInterval(id);
  }, [clip, paused]);

  useEffect(() => {
    if (clip && elapsed >= reelClipLengthMs(clip)) {
      setClipIndex((i) => i + 1);
      setElapsed(0);
    }
  }, [clip, elapsed]);

  // Speak each clip once per start, even if effects re-run (React strict mode runs them twice in development).
  const playKey = clip ? `${clipIndex}:${clip.moment_id}` : null;
  useEffect(() => {
    if (!clip || !voiceOn || spoken.current === playKey) return;
    spoken.current = playKey;
    speakLine(clip.commentary, clip.language, clip.intensity, REEL_RATE);
  }, [clip, voiceOn, playKey]);

  const goTo = (index: number) => {
    stopSpeaking();
    spoken.current = null;
    setClipIndex(Math.max(0, Math.min(index, clips.length)));
    setElapsed(0);
    setPaused(false);
  };

  const view = useMemo(() => (clip ? reelView(clip, elapsed, TICK_MS) : null), [clip, elapsed]);
  const dots = useMemo(() => (view
    ? playerDots(match, view.positions, { actor: view.actor, receiver: view.receiver }, null, NO_SPRINT) : []),
  [match, view]);

  if (error) return <div className="panel empty" role="alert">{error}</div>;
  if (!reel) return <div className="panel empty">Cutting the highlights...</div>;
  const label = stage === "half_time" ? "Half-time highlights" : "Full-time highlights";

  return (
    <section className="stack" aria-label={label}>
      {finished || !clip || !view ? (
        <div className="panel empty stack">
          <h2 className="display" style={{ margin: 0 }}>{clips.length ? "End of highlights" : "No highlights yet"}</h2>
          <p className="muted" style={{ margin: 0 }}>{reel.headline}</p>
        </div>
      ) : (
        <PitchView ball={view.ball} trail={[]} players={dots} moveMs={view.moveMs} homeColor={homeColor}
          awayColor={awayColor} camera={camera} shot={null} onBallAnchor={onBallAnchor}
          label={`${label}: ${clip.minute} ${clip.title}`}>
          <div aria-live="polite"
            className={`glass highlight-caption at-${placement}${compact ? ` ${COMPACT_CLASS}` : ""}`}>
            <CaptionBody label={label} position={clipIndex + 1} count={clips.length} clip={clip} />
          </div>
          <div ref={fullRef} aria-hidden="true" className={`glass highlight-caption at-top ${MEASURE_CLASS}`}>
            <CaptionBody label={label} position={clipIndex + 1} count={clips.length} clip={clip} />
          </div>
          <div ref={compactRef} aria-hidden="true"
            className={`glass highlight-caption at-top-left ${COMPACT_CLASS} ${MEASURE_CLASS}`}>
            <CaptionBody label={label} position={clipIndex + 1} count={clips.length} clip={clip} />
          </div>
        </PitchView>
      )}
      <div className="highlight-controls" role="group" aria-label="Highlights controls">
        <button className="tab" onClick={() => goTo(clipIndex - 1)} disabled={clipIndex === 0}>Previous</button>
        {finished
          ? <button className="tab" onClick={() => goTo(0)}>Replay</button>
          : <button className="tab" aria-pressed={paused} onClick={() => setPaused((p) => !p)}>{paused ? "Play" : "Pause"}</button>}
        <button className="tab" onClick={() => goTo(clipIndex + 1)} disabled={finished}>Next</button>
        <button className="button-primary" onClick={onClose}>Back to live</button>
      </div>
    </section>
  );
}
