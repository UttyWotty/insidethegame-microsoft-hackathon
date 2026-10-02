/**
 * The main broadcast experience: the live pitch with persona overlays, score bug, stats, momentum, and commentary.
 * It subscribes to the viewer's personalized stream and opens the recap dialog when a new recap arrives.
 * Changing persona or language reconnects to a different segment of the same live match.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useMatchStream } from "../api/useMatchStream";
import { teamColor } from "../lib/teams";
import { useNow } from "../lib/useNow";
import { activeCue } from "../state/matchState";
import type { MatchEvent, MatchMetadata, Point, Recap, ViewerSettings } from "../types";

type Camera = "broadcast" | "tactical";

const SHOT_VISIBLE_MS = 4000;
const HALF_TIME_RECAP_MS = 15000;
const GOAL_VISIBLE_MS = 4500;

function playerDots(match: MatchMetadata | undefined, positions: Record<string, Point>, last: MatchEvent | null,
                    tracked: string | null): PlayerDot[] {
  if (!match) return [];
  const tagged = new Set([last?.player_id, last?.receiver_id].filter(Boolean));
  return [match.home, match.away].flatMap((team, i) => team.players
    .filter((p) => positions[p.player_id])
    .map((p) => ({
      id: p.player_id, number: p.shirt_number, shortName: p.name.split(" ").slice(-1)[0],
      side: i === 0 ? "home" as const : "away" as const, position: positions[p.player_id],
      goalkeeper: p.position === "GK", tagged: tagged.has(p.player_id), tracked: p.player_id === tracked,
      tagBelow: p.player_id === last?.receiver_id,
    })));
}
import { AskPanel } from "./AskPanel";
import { CommentaryTicker } from "./CommentaryTicker";
import { MomentumChart } from "./MomentumChart";
import { OverlayLayer } from "./overlays/OverlayLayer";
import { GoalBanner } from "./overlays/Overlays";
import { Pitch, type BallAnchor, type PlayerDot } from "./Pitch";
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
  const dots = useMemo(() => playerDots(state.session?.match, state.players, state.lastEvent, viewer.player),
    [state.session, state.players, state.lastEvent, viewer.player]);
  const [seenStages, setSeenStages] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const fresh = state.recaps.find((r) => !seenStages.has(r.stage));
    if (fresh) {
      setOpenRecap(fresh);
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
        <Pitch ball={state.ball} trail={state.trail} players={dots} homeColor={homeColor} awayColor={awayColor}
          camera={camera} shot={shot} onBallAnchor={onBallAnchor} label={`Live pitch: ${match.home.name} versus ${match.away.name}`}>
          <ScoreBug home={match.home} away={match.away} homeColor={homeColor} awayColor={awayColor} lastEvent={state.lastEvent} />
          <OverlayLayer active={goal ? null : active} anchor={anchor} teamColor={cueTeamIsAway ? awayColor : homeColor} />
          {goal && <GoalBanner key={goal.id} scorer={goal.scorer} score={goal.score}
            teamColor={goal.side === "home" ? homeColor : awayColor} />}
        </Pitch>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          {status === "open" && !state.ended && <span className="chip chip--live">LIVE</span>}
          <div className="tabs camera-toggle" role="group" aria-label="Camera">
            {(["broadcast", "tactical"] as Camera[]).map((c) => (
              <button key={c} className="tab" aria-pressed={camera === c} onClick={() => setCamera(c)}>
                {c === "broadcast" ? "Broadcast cam" : "Tactical"}
              </button>
            ))}
          </div>
          {state.ended && <span className="chip">FULL TIME</span>}
          <span className="muted" style={{ fontSize: "var(--text-sm)" }}>{match.venue} - {match.competition}</span>
          {state.recaps.map((r) => (
            <button key={r.stage} className="chip" onClick={() => setOpenRecap(r)}>
              {r.stage === "half_time" ? "Half-time recap" : "Full-time recap"}
            </button>
          ))}
        </div>
        <CommentaryTicker items={state.ticker} />
      </div>
      <aside className="rail">
        <AskPanel sessionId={sessionId} viewer={viewer} />
        <StatsPanel snapshot={state.snapshot} homeColor={homeColor} awayColor={awayColor} />
        <MomentumChart points={state.momentum} rhythm={state.rhythm} homeColor={homeColor} awayColor={awayColor}
          homeName={match.home.short_name} awayName={match.away.short_name} />
      </aside>
      {openRecap && <RecapModal recap={openRecap} onClose={() => setOpenRecap(null)} />}
    </>
  );
}
