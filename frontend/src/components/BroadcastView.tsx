/**
 * The main broadcast experience: the live pitch with persona overlays, score bug, stats, momentum, and commentary.
 * It subscribes to the viewer's personalized stream and opens the recap dialog when a new recap arrives.
 * Changing persona or language reconnects to a different segment of the same live match.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { useMatchStream } from "../api/useMatchStream";
import { sprintSpeed } from "../lib/motion";
import { playerDots } from "../lib/playerDots";
import { earnsReplay, REPLAY_DELAY_MS } from "../lib/replay";
import { teamColor } from "../lib/teams";
import { useNow } from "../lib/useNow";
import { speechSupported, useSpokenCommentary, type SpeechUrlBuilder } from "../lib/useSpokenCommentary";
import { activeCue, type ShotTrace } from "../state/matchState";
import type { HighlightReel, Recap, ViewerSettings } from "../types";


const SHOT_VISIBLE_MS = 4000;
const HALF_TIME_RECAP_MS = 15000;
const GOAL_VISIBLE_MS = 4500;
/** Replay speed assumed for speech pace until the session description arrives (the server default). */
const DEFAULT_MATCH_SPEED = 10;
const VOICE_PREFERENCE_KEY = "inside-the-game.voice";

/** Whether the viewer last left voice on; storage can be unavailable (private mode), which reads as off. */
function savedVoicePreference(): boolean {
  try {
    return window.localStorage.getItem(VOICE_PREFERENCE_KEY) === "on";
  } catch {
    return false;
  }
}

function saveVoicePreference(on: boolean): void {
  try {
    window.localStorage.setItem(VOICE_PREFERENCE_KEY, on ? "on" : "off");
  } catch {
    // Storage is a convenience only; the toggle still works for this match.
  }
}
const TYPING_ELEMENTS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** True while the viewer is typing in a field, when a recap dialog must not take focus away. */
function isTyping(): boolean {
  return TYPING_ELEMENTS.has(document.activeElement?.tagName ?? "");
}

import { AskPanel } from "./AskPanel";
import { CommentaryTicker } from "./CommentaryTicker";
import { MomentumChart } from "./MomentumChart";
import { OverlayLayer } from "./overlays/OverlayLayer";
import { GoalBanner } from "./overlays/Overlays";
import { HighlightsPlayer } from "./HighlightsPlayer";
import { ReplayPlayer } from "./ReplayPlayer";
import { type BallAnchor } from "./Pitch";
import { PitchView, type Camera } from "./PitchView";
import { RecapModal } from "./RecapModal";
import { ScoreBug } from "./ScoreBug";
import { StatsPanel } from "./StatsPanel";

export function BroadcastView({ sessionId, viewer }: { sessionId: string; viewer: ViewerSettings }) {
  const [state, status] = useMatchStream(sessionId, viewer);
  const now = useNow();
  const [openRecap, setOpenRecap] = useState<Recap | null>(null);
  const [camera, setCamera] = useState<Camera>("broadcast");
  const [anchor, setAnchor] = useState<BallAnchor>(null);
  const onBallAnchor = useCallback((next: BallAnchor) => setAnchor(next), []);
  const dots = useMemo(() => playerDots(state.session?.match, state.players,
    { actor: state.lastEvent?.player_id ?? null, receiver: state.lastEvent?.receiver_id ?? null }, viewer.player,
    (id) => sprintSpeed(state.sprint, id, now)),
  [state.session, state.players, state.lastEvent, viewer.player, state.sprint, now]);
  const [reelStage, setReelStage] = useState<HighlightReel["stage"] | null>(null);
  const [autoReplay, setAutoReplay] = useState(true);
  const [replayShot, setReplayShot] = useState<ShotTrace | null>(null);
  const lastShot = state.lastShot;
  const replayTimers = useRef<number[]>([]);
  // A qualifying shot's replay is not cancelled by later shots; it only waits for any replay already rolling.
  useEffect(() => {
    if (!autoReplay || !lastShot || !earnsReplay(lastShot)) return;
    replayTimers.current.push(window.setTimeout(() => setReplayShot((current) => current ?? lastShot), REPLAY_DELAY_MS));
  }, [autoReplay, lastShot]);
  useEffect(() => {
    const timers = replayTimers.current;
    if (!autoReplay) timers.splice(0).forEach((id) => window.clearTimeout(id));
    return () => timers.splice(0).forEach((id) => window.clearTimeout(id));
  }, [autoReplay]);
  const [seenStages, setSeenStages] = useState<Set<string>>(() => new Set());
  const [voiceOn, setVoiceOn] = useState(savedVoicePreference);
  const [neuralVoice, setNeuralVoice] = useState(false);
  const toggleVoice = useCallback(() => setVoiceOn((on) => {
    saveVoicePreference(!on);
    return !on;
  }), []);
  useEffect(() => {
    api.speechStatus().then((s) => setNeuralVoice(s.available)).catch(() => setNeuralVoice(false));
  }, []);
  const speechUrl = useMemo<SpeechUrlBuilder>(
    () => (neuralVoice ? (ref, segment) => api.speechUrl(sessionId, ref, segment) : null), [neuralVoice, sessionId]);
  const matchSpeed = state.session?.speed ?? DEFAULT_MATCH_SPEED;
  useSpokenCommentary(state.ticker, viewer.language, voiceOn && !reelStage && !replayShot, matchSpeed, speechUrl);

  useEffect(() => {
    const fresh = state.recaps.find((r) => !seenStages.has(r.stage));
    if (fresh) {
      if (!isTyping()) setOpenRecap(fresh);
      setSeenStages((current) => new Set(current).add(fresh.stage));
    }
  }, [state.recaps, seenStages]);

  useEffect(() => {
    if (openRecap?.stage !== "half_time") return undefined;
    const id = window.setTimeout(() => setOpenRecap(null), HALF_TIME_RECAP_MS);
    return () => window.clearTimeout(id);
  }, [openRecap]);

  const match = state.session?.match;
  if (!match) return <div className="panel empty">Connecting to the live match ({status})...</div>;
  const homeColor = teamColor(match.home.team_id, true);
  const awayColor = teamColor(match.away.team_id, false);
  const clock = state.lastEvent ? { period: state.lastEvent.period, second: state.lastEvent.match_second } : null;
  const active = activeCue(state.cues, now, clock);
  const cueTeamIsAway = active && viewer.team === match.away.team_id;
  const shot = state.lastShot && now - state.lastShot.at < SHOT_VISIBLE_MS ? state.lastShot : null;
  const goal = state.goalFlash && now - state.goalFlash.at < GOAL_VISIBLE_MS ? state.goalFlash : null;

  return (
    <>
      <div className="stage">
        {replayShot && !reelStage ? (
          <ReplayPlayer key={replayShot.id} sessionId={sessionId} shot={replayShot} match={match} homeColor={homeColor}
            awayColor={awayColor} camera={camera} voiceOn={voiceOn} language={viewer.language}
            onDone={() => setReplayShot(null)} />
        ) : reelStage ? (
          <HighlightsPlayer sessionId={sessionId} stage={reelStage} segment={state.cues[0]?.cue.viewer_id} match={match}
            homeColor={homeColor} awayColor={awayColor} camera={camera} voiceOn={voiceOn} onClose={() => setReelStage(null)} />
        ) : (
          <PitchView ball={state.ball} trail={state.trail} players={dots} moveMs={state.moveMs} homeColor={homeColor} awayColor={awayColor}
            camera={camera} shot={shot} onBallAnchor={onBallAnchor} label={`Live pitch: ${match.home.name} versus ${match.away.name}`}>
            <ScoreBug home={match.home} away={match.away} homeColor={homeColor} awayColor={awayColor} lastEvent={state.lastEvent} />
            <OverlayLayer active={goal ? null : active} anchor={anchor} teamColor={cueTeamIsAway ? awayColor : homeColor} />
            {goal && <GoalBanner key={goal.id} scorer={goal.scorer} score={goal.score}
              teamColor={goal.side === "home" ? homeColor : awayColor} />}
          </PitchView>
        )}
        <p className="visually-hidden" aria-live="assertive">
          {state.goalFlash ? `Goal, ${state.goalFlash.scorer}. ${state.goalFlash.score}` : ""}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", alignItems: "center" }}>
          {status === "open" && !state.ended && <span className="chip chip--live">LIVE</span>}
          <div className="tabs camera-toggle" role="group" aria-label="Camera">
            {(["broadcast", "tactical", "3d"] as Camera[]).map((c) => (
              <button key={c} className="tab" aria-pressed={camera === c} onClick={() => setCamera(c)}>
                {{ broadcast: "Broadcast cam", tactical: "Tactical", "3d": "3D" }[c]}
              </button>
            ))}
          </div>
          <button className="chip" aria-pressed={autoReplay} onClick={() => setAutoReplay((on) => !on)}>Auto replays</button>
          {state.ended && <span className="chip">FULL TIME</span>}
          <span className="muted" style={{ fontSize: "var(--text-sm)" }}>{match.venue} - {match.competition}</span>
          {state.recaps.map((r) => (
            <button key={r.stage} className="chip" onClick={() => setOpenRecap(r)}>
              {r.stage === "half_time" ? "Half-time recap" : "Full-time recap"}
            </button>
          ))}
          {state.recaps.map((r) => (
            <button key={`${r.stage}-reel`} className="chip" aria-pressed={reelStage === r.stage}
              onClick={() => setReelStage(r.stage)}>
              {r.stage === "half_time" ? "Half-time highlights" : "Full-time highlights"}
            </button>
          ))}
        </div>
        <CommentaryTicker items={state.ticker}
          voice={speechSupported || neuralVoice ? { on: voiceOn, onToggle: toggleVoice } : undefined} />
      </div>
      <aside className="rail">
        <AskPanel sessionId={sessionId} viewer={viewer} />
        <StatsPanel snapshot={state.snapshot} homeColor={homeColor} awayColor={awayColor} />
        <MomentumChart points={state.momentum} rhythm={state.rhythm} homeColor={homeColor} awayColor={awayColor}
          homeName={match.home.short_name} awayName={match.away.short_name} />
      </aside>
      {openRecap && <RecapModal recap={openRecap} onClose={() => setOpenRecap(null)}
        onWatch={() => { setReelStage(openRecap.stage); setOpenRecap(null); }} />}
    </>
  );
}
