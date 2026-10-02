/**
 * The main broadcast experience: the live pitch with persona overlays, score bug, stats, momentum, and commentary.
 * It subscribes to the viewer's personalized stream and opens the recap dialog when a new recap arrives.
 * Changing persona or language reconnects to a different segment of the same live match.
 */
import { useEffect, useState } from "react";
import { useMatchStream } from "../api/useMatchStream";
import { teamColor } from "../lib/teams";
import { useNow } from "../lib/useNow";
import { activeCue } from "../state/matchState";
import type { Recap, ViewerSettings } from "../types";
import { AskPanel } from "./AskPanel";
import { CommentaryTicker } from "./CommentaryTicker";
import { MomentumChart } from "./MomentumChart";
import { OverlayLayer } from "./overlays/OverlayLayer";
import { Pitch } from "./Pitch";
import { RecapModal } from "./RecapModal";
import { ScoreBug } from "./ScoreBug";
import { StatsPanel } from "./StatsPanel";

export function BroadcastView({ sessionId, viewer }: { sessionId: string; viewer: ViewerSettings }) {
  const [state, status] = useMatchStream(sessionId, viewer);
  const now = useNow();
  const [openRecap, setOpenRecap] = useState<Recap | null>(null);
  const [seenStages, setSeenStages] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const fresh = state.recaps.find((r) => !seenStages.has(r.stage));
    if (fresh) {
      setOpenRecap(fresh);
      setSeenStages((current) => new Set(current).add(fresh.stage));
    }
  }, [state.recaps, seenStages]);

  const match = state.session?.match;
  if (!match) return <div className="panel empty">Connecting to the live match ({status})...</div>;
  const homeColor = teamColor(match.home.team_id, true);
  const awayColor = teamColor(match.away.team_id, false);
  const clock = state.lastEvent ? { period: state.lastEvent.period, second: state.lastEvent.match_second } : null;
  const active = activeCue(state.cues, now, clock);
  const cueTeamIsAway = active && viewer.team === match.away.team_id;

  return (
    <>
      <div className="stage">
        <Pitch ball={state.ball} trail={state.trail} homeColor={homeColor} awayColor={awayColor}
          label={`Live pitch: ${match.home.name} versus ${match.away.name}`}>
          <ScoreBug home={match.home} away={match.away} homeColor={homeColor} awayColor={awayColor} lastEvent={state.lastEvent} />
          <OverlayLayer active={active} ball={state.ball} teamColor={cueTeamIsAway ? awayColor : homeColor} />
        </Pitch>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          {status === "open" && !state.ended && <span className="chip chip--live">LIVE</span>}
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
