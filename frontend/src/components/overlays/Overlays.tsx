/**
 * The five broadcast overlay layouts, one per persona style, rendered over the pitch.
 * Each layout reads the same cue contract but presents it differently: stat panel, lower third, hype banner,
 * player tag anchored to the ball, and an explainer card.
 */
import type { CSSProperties } from "react";
import { PITCH_LENGTH, PITCH_WIDTH } from "../../lib/pitch";
import type { OverlayCue, Point } from "../../types";
import { ProvenanceBadge } from "../ProvenanceBadge";

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

export function PlayerTag({ cue, ball }: { cue: OverlayCue; ball: Point | null }) {
  const anchor = ball ?? { x: PITCH_LENGTH / 2, y: PITCH_WIDTH / 2 };
  const style = { left: `${(anchor.x / PITCH_LENGTH) * PERCENT}%`, top: `${(anchor.y / PITCH_WIDTH) * PERCENT}%` };
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
