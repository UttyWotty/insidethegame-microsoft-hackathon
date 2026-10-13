/**
 * The five broadcast overlay layouts, one per persona style, rendered over the pitch.
 * Each layout reads the same cue contract but presents it differently: stat panel, lower third, hype banner,
 * player tag anchored to the ball, and an explainer card.
 */
import type { CSSProperties } from "react";
import type { OverlayCue } from "../../types";
import { FactCheckBadge, ProvenanceBadge } from "../ProvenanceBadge";

const PERCENT = 100;

function Callouts({ cue }: { cue: OverlayCue }) {
  if (!cue.stat_callouts.length) return null;
  return (
    <div className="callouts">
      {cue.stat_callouts.map((c) => (
        <div className="callout" key={c.label}><b className="num">{c.value}</b><span>{c.label}</span></div>
      ))}
    </div>
  );
}

function Meta({ cue }: { cue: OverlayCue }) {
  return (
    <div className="overlay-meta">
      <ProvenanceBadge provenance={cue.provenance.card} />
      <FactCheckBadge check={cue.provenance.fact_check} />
      {cue.language !== "en" && <span className="chip">{cue.language.toUpperCase()}</span>}
    </div>
  );
}

export function StatPanel({ cue }: { cue: OverlayCue }) {
  return (
    <section className="glass ov-stat-panel" aria-label="Analyst panel">
      <h3 className="overlay-title">{cue.title}</h3>
      <p className="overlay-body">{cue.body}</p>
      <Callouts cue={cue} />
      <Meta cue={cue} />
    </section>
  );
}

export function LowerThird({ cue }: { cue: OverlayCue }) {
  return (
    <section className="glass ov-lower-third" aria-label="Lower third">
      <h3 className="overlay-title">{cue.title}</h3>
      <p className="overlay-body">{cue.body}</p>
    </section>
  );
}

export function HypeBanner({ cue, teamColor }: { cue: OverlayCue; teamColor: string }) {
  return (
    <section className="glass ov-hype-banner" aria-label="Supporter banner" style={{ "--team-color": teamColor } as CSSProperties}>
      <h3 className="overlay-title">{cue.title}</h3>
      <p className="overlay-body">{cue.body}</p>
      <Meta cue={cue} />
    </section>
  );
}

export function PlayerTag({ cue, anchor }: { cue: OverlayCue; anchor: { left: string; top: string } | null }) {
  const style = anchor ?? { left: `${PERCENT / 2}%`, top: `${PERCENT / 2}%` };
  return (
    <section className="glass ov-player-tag" aria-label="Player tag" style={style}>
      <h3 className="overlay-title">{cue.title}</h3>
      <p className="overlay-body">{cue.body}</p>
      <Callouts cue={cue} />
    </section>
  );
}

export function ExplainerCard({ cue }: { cue: OverlayCue }) {
  return (
    <section className="glass ov-explainer" aria-label="Explainer">
      <span className="term">Learn the game</span>
      <h3 className="overlay-title">{cue.title}</h3>
      <p className="overlay-body">{cue.body}</p>
      <Meta cue={cue} />
    </section>
  );
}

export function GoalBanner({ scorer, score, teamColor }: { scorer: string; score: string; teamColor: string }) {
  return (
    <section className="goal-banner" aria-hidden="true" style={{ "--team-color": teamColor } as CSSProperties}>
      <span className="goal-word">GOAL</span>
      <span className="goal-detail">{scorer} <span className="num">{score}</span></span>
    </section>
  );
}
