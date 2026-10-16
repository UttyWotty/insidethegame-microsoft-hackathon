/**
 * Instant replay of a goal or big chance as a story from the server: the build-up passes and carries at real pace,
 * the strike and the ball's flight into the goal mouth in slow motion, then a hold on the analysis card.
 * The 2D crop frames the whole action and draws the build-up path and shot cone under the players; the REPLAY bug,
 * a short commentator line, and the "Back to live" button stay, and the live broadcast resumes when the replay ends.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { toScreen } from "../lib/pitch";
import { playerDots } from "../lib/playerDots";
import { goalEnd, REPLAY_SPEECH_RATE, replayLine } from "../lib/replay";
import { coneScreen, pathScreen } from "../lib/replayAnalysis";
import { cardSide, replayCrop } from "../lib/replayFraming";
import { clockAt, replayLengthMs, replayStage, sampleAt } from "../lib/replayTimeline";
import { speakLine, stopSpeaking } from "../lib/speakLine";
import type { ShotTrace } from "../state/matchState";
import type { MatchMetadata, PersonaKey, Point, ReplayStory } from "../types";
import { ReplayAnalysisCard } from "./overlays/ReplayAnalysisCard";
import { ReplayAnalysisLayer } from "./overlays/ReplayAnalysisLayer";
import { type BallAnchor } from "./Pitch";
import { PitchView, type Camera } from "./PitchView";

const TICK_MS = 50;
const NO_SPRINT = () => null;
const RESULT_TITLES: Record<string, string> = { goal: "Goal", saved: "Saved", off_target: "Wide", blocked: "Blocked" };

interface ReplayPlayerProps {
  sessionId: string; shot: ShotTrace; match: MatchMetadata; homeColor: string; awayColor: string; camera: Camera;
  voiceOn: boolean; language: string; persona: PersonaKey; onDone: () => void;
}

export function ReplayPlayer(props: ReplayPlayerProps) {
  const { sessionId, shot, match, homeColor, awayColor, camera, voiceOn, language, persona, onDone } = props;
  const [story, setStory] = useState<ReplayStory | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(onDone);
  done.current = onDone;
  const onBallAnchor = useCallback((_: BallAnchor) => undefined, []);

  useEffect(() => {
    let live = true;
    api.replay(sessionId, shot.period, shot.second)
      .then((r) => { if (live) (r.frames.length ? setStory(r) : done.current()); })
      .catch(() => live && done.current());
    if (voiceOn) speakLine(replayLine(shot), language, "normal", REPLAY_SPEECH_RATE);
    return () => { live = false; stopSpeaking(); };
  }, [sessionId, shot, voiceOn, language]);

  useEffect(() => {
    if (!story) return undefined;
    const id = window.setInterval(() => setElapsed((ms) => ms + TICK_MS), TICK_MS);
    return () => window.clearInterval(id);
  }, [story]);

  useEffect(() => {
    if (story && elapsed >= replayLengthMs(story.frames)) done.current();
  }, [story, elapsed]);

  const names = useMemo(() => Object.fromEntries([...match.home.players, ...match.away.players]
    .map((p) => [p.player_id, p.name])), [match]);
  const framing = useMemo(() => {
    if (!story) return null;
    const { analysis: a, frames: keys, period: half } = story;
    const last = keys[keys.length - 1];
    const landing = toScreen({ x: last.ball[0], y: last.ball[1] }, true, half);
    const strike = coneScreen(a, half);
    const goal = goalEnd(keys);
    const action = [...pathScreen(a, half, a.build_up.path.length), ...strike, landing];
    return { zoom: replayCrop(action, [...strike, landing], goal), behindGoal: goal };
  }, [story]);

  const frames = story?.frames ?? [];
  const sample = frames.length ? sampleAt(frames, clockAt(frames, elapsed)) : null;
  const period = story?.period ?? shot.period;
  const screen = (p: Point) => toScreen(p, true, period);

  if (!story || !sample || !framing) return <div className="pitch-wrap replay-loading">Cueing the replay...</div>;
  const positions = Object.fromEntries(sample.positions.map(([id, x, y]) => [id, screen({ x, y })]));
  const focus = { actor: sample.actor, receiver: frames[sample.index].receiver_id };
  const dots = playerDots(match, positions, focus, null, NO_SPRINT);
  const analysis = story.analysis;
  const stage = replayStage(frames, elapsed);
  const ball = screen(sample.ball);
  const color = analysis.team_id === match.home.team_id ? homeColor : awayColor;
  const path = stage === "build_up" ? [...pathScreen(analysis, period, sample.index), ball]
    : pathScreen(analysis, period, analysis.build_up.path.length);
  const annotations = camera !== "3d"
    ? <ReplayAnalysisLayer cone={stage === "build_up" ? null : coneScreen(analysis, period)} path={path} color={color} />
    : null;
  const shooter = names[shot.shooter ?? ""];
  const title = RESULT_TITLES[shot.result] ?? "Chance";
  const side = cardSide(framing.behindGoal);
  return (
    <section className="stack replay-stage" aria-label="Instant replay">
      <PitchView camera={camera} ball={ball} trail={[]} players={dots} moveMs={TICK_MS} homeColor={homeColor}
        awayColor={awayColor} shot={null} onBallAnchor={onBallAnchor} replay={framing} annotations={annotations}
        label={`Instant replay: ${title}${shooter ? `, ${shooter}` : ""}`}>
        <div className="replay-bug" aria-hidden="true">REPLAY</div>
        <ReplayAnalysisCard stage={stage} analysis={analysis} persona={persona} names={names} color={color}
          side={side} />
        <div className={`glass replay-caption side-${side}`} aria-live="polite">
          <strong className="display">{title}{shooter ? ` - ${shooter}` : ""}</strong>
        </div>
      </PitchView>
      <div className="highlight-controls">
        <span className="chip">{stage === "shot" ? "Slow motion" : stage === "analysis" ? "Analysis" : "Build-up"}</span>
        <button className="button-primary" onClick={() => done.current()}>Back to live</button>
      </div>
    </section>
  );
}
