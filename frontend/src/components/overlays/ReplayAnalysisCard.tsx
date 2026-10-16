/**
 * HTML analysis card of an instant replay, layered over the pitch on the half away from the attacked goal.
 * It follows the replay's stage, and during the build-up a chip names the build-up and the assist.
 * During the strike it shows xG, goal chance, distance, and angle, then the persona's full rows once the ball arrives.
 */
import { analysisRows, assistLabel, buildUpLabel, replayXg } from "../../lib/replayAnalysis";
import type { CardSide } from "../../lib/replayFraming";
import type { ReplayStage } from "../../lib/replayTimeline";
import { shotStats } from "../../lib/shotCard";
import type { PersonaKey, ReplayAnalysis } from "../../types";

interface ReplayAnalysisCardProps {
  stage: ReplayStage; analysis: ReplayAnalysis; persona: PersonaKey; names: Record<string, string>; color: string;
  /** The half of the view away from the attacked goal, where the card sits. */
  side: CardSide;
}

const STRIKE_STATS = new Set(["Distance", "Angle"]);

/** The replay xG and goal chance (from the same value), then distance and angle in the shot card's formats. */
function strikeRows(a: ReplayAnalysis): [string, string][] {
  const rows = shotStats(a.card).filter(([label]) => STRIKE_STATS.has(label));
  return [["xG", replayXg(a)], ["Goal chance", `${a.goal_chance_pct}%`], ...rows];
}

export function ReplayAnalysisCard({ stage, analysis, persona, names, color, side }: ReplayAnalysisCardProps) {
  if (stage === "build_up") {
    const assist = assistLabel(analysis, names);
    return (
      <div className={`glass replay-analysis replay-chip side-${side}`} style={{ borderLeftColor: color }}>
        <strong>Build-up: {buildUpLabel(analysis)}</strong>
        {assist && <span>Assist: {assist}</span>}
      </div>
    );
  }
  const rows = stage === "shot" ? strikeRows(analysis) : analysisRows(analysis, persona, names);
  return (
    <aside className={`glass replay-analysis side-${side}`} style={{ borderTopColor: color }} aria-label="Replay analysis">
      <dl>
        {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
    </aside>
  );
}
