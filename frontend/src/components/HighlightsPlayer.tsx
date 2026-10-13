/**
 * Automated highlights reel: replays each key moment on the pitch from stored tracking frames.
 * Players and the ball move at real match pace, a broadcast lower third captions the clip, and the commentator
 * narrates it when Voice is on. Viewers can pause, skip between clips, replay, or go back to the live match.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { playerDots } from "../lib/playerDots";
import { clipLengthMs, frameBall, frameIndexAt, framePositions, glideMs, REEL_RATE } from "../lib/reel";
import { speakLine, stopSpeaking } from "../lib/speakLine";
import type { HighlightReel, MatchMetadata } from "../types";
import { Pitch, type BallAnchor } from "./Pitch";

const TICK_MS = 100;
const NO_SPRINT = () => null;

interface HighlightsPlayerProps {
  sessionId: string; stage: HighlightReel["stage"]; segment?: string; match: MatchMetadata;
  homeColor: string; awayColor: string; camera: "broadcast" | "tactical"; voiceOn: boolean; onClose: () => void;
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

  useEffect(() => {
    if (!clip || paused) return undefined;
    const id = window.setInterval(() => setElapsed((ms) => ms + TICK_MS), TICK_MS);
    return () => window.clearInterval(id);
  }, [clip, paused]);

  useEffect(() => {
    if (clip && elapsed >= clipLengthMs(clip)) {
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

  const frameIndex = clip ? frameIndexAt(clip, elapsed) : 0;
  const frame = clip?.frames[frameIndex];
  const dots = useMemo(() => (frame
    ? playerDots(match, framePositions(frame), { actor: frame.player_id, receiver: null }, null, NO_SPRINT) : []),
  [match, frame]);

  if (error) return <div className="panel empty" role="alert">{error}</div>;
  if (!reel) return <div className="panel empty">Cutting the highlights...</div>;
  const label = stage === "half_time" ? "Half-time highlights" : "Full-time highlights";

  return (
    <section className="stack" aria-label={label}>
      {finished || !clip || !frame ? (
        <div className="panel empty stack">
          <h2 className="display" style={{ margin: 0 }}>{clips.length ? "End of highlights" : "No highlights yet"}</h2>
          <p className="muted" style={{ margin: 0 }}>{reel.headline}</p>
        </div>
      ) : (
        <Pitch ball={frameBall(frame)} trail={[]} players={dots} moveMs={glideMs(clip, frameIndex)} homeColor={homeColor}
          awayColor={awayColor} camera={camera} shot={null} onBallAnchor={onBallAnchor}
          label={`${label}: ${clip.minute} ${clip.title}`}>
          <div className="glass highlight-caption" aria-live="polite">
            <span className="term">{label} - {clipIndex + 1} of {clips.length}</span>
            <strong className="display highlight-title">{clip.minute} {clip.title}{clip.actor ? ` - ${clip.actor}` : ""}</strong>
            <span>{clip.commentary}</span>
          </div>
        </Pitch>
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
