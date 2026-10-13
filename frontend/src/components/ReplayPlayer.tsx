/**
 * Instant replay of a goal or big chance: the stored frames around the shot play again in slow motion from
 * another angle (behind the goal in 3D, a zoomed crop in 2D), under a REPLAY bug, with a short commentator line,
 * then hand back to the live broadcast. Viewers can skip back to live at any time.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { playerDots } from "../lib/playerDots";
import { clipLengthMs, frameBall, frameIndexAt, framePositions, glideMs, type Playable } from "../lib/reel";
import { goalEnd, REPLAY_MAX_GLIDE_MS, REPLAY_RATE, replayLine, zoomBox } from "../lib/replay";
import { speakLine, stopSpeaking } from "../lib/speakLine";
import type { ShotTrace } from "../state/matchState";
import type { MatchMetadata } from "../types";
import { type BallAnchor } from "./Pitch";
import { PitchView, type Camera } from "./PitchView";

const TICK_MS = 50;
const NO_SPRINT = () => null;
const RESULT_TITLES: Record<string, string> = { goal: "Goal", saved: "Saved", off_target: "Wide", blocked: "Blocked" };

interface ReplayPlayerProps {
  sessionId: string; shot: ShotTrace; match: MatchMetadata; homeColor: string; awayColor: string; camera: Camera;
  voiceOn: boolean; language: string; onDone: () => void;
}

export function ReplayPlayer(props: ReplayPlayerProps) {
  const { sessionId, shot, match, homeColor, awayColor, camera, voiceOn, language, onDone } = props;
  const [clip, setClip] = useState<Playable | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(onDone);
  done.current = onDone;
  const onBallAnchor = useCallback((_: BallAnchor) => undefined, []);

  useEffect(() => {
    let live = true;
    api.replay(sessionId, shot.period, shot.second)
      .then((r) => { if (live) (r.frames.length ? setClip({ frames: r.frames }) : done.current()); })
      .catch(() => live && done.current());
    if (voiceOn) speakLine(replayLine(shot), language, "normal", REPLAY_RATE);
    return () => { live = false; stopSpeaking(); };
  }, [sessionId, shot, voiceOn, language]);

  useEffect(() => {
    if (!clip) return undefined;
    const id = window.setInterval(() => setElapsed((ms) => ms + TICK_MS), TICK_MS);
    return () => window.clearInterval(id);
  }, [clip]);

  useEffect(() => {
    if (clip && elapsed >= clipLengthMs(clip, REPLAY_RATE)) done.current();
  }, [clip, elapsed]);

  const index = clip ? frameIndexAt(clip, elapsed, REPLAY_RATE) : 0;
  const frame = clip?.frames[index];
  const framing = useMemo(() => (clip ? {
    zoom: zoomBox(frameBall(clip.frames[clip.frames.length - 1])), behindGoal: goalEnd(clip.frames),
  } : null), [clip]);
  const dots = useMemo(() => (frame
    ? playerDots(match, framePositions(frame), { actor: frame.player_id, receiver: null }, null, NO_SPRINT) : []),
  [match, frame]);
  const shooter = [...match.home.players, ...match.away.players].find((p) => p.player_id === shot.shooter)?.name;

  if (!clip || !frame) return <div className="pitch-wrap replay-loading">Cueing the replay...</div>;
  return (
    <section className="stack" aria-label="Instant replay">
      <PitchView camera={camera} ball={frameBall(frame)} trail={[]} players={dots}
        moveMs={glideMs(clip, index, REPLAY_RATE, REPLAY_MAX_GLIDE_MS)} homeColor={homeColor} awayColor={awayColor}
        shot={null} onBallAnchor={onBallAnchor} replay={framing}
        label={`Instant replay: ${RESULT_TITLES[shot.result] ?? "Chance"}${shooter ? `, ${shooter}` : ""}`}>
        <div className="replay-bug" aria-hidden="true">REPLAY</div>
        <div className="glass replay-caption" aria-live="polite">
          <strong className="display">{RESULT_TITLES[shot.result] ?? "Chance"}{shooter ? ` - ${shooter}` : ""}</strong>
          {shot.xg !== null && <span>xG {shot.xg.toFixed(2)}</span>}
        </div>
      </PitchView>
      <div className="highlight-controls">
        <span className="chip">Slow motion</span>
        <button className="button-primary" onClick={() => done.current()}>Back to live</button>
      </div>
    </section>
  );
}
