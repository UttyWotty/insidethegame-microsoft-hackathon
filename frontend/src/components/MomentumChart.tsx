/**
 * Diverging momentum chart: the home side's threat above the centre line and the away side's below.
 * Samples arrive every 30 match seconds, so the series stays small enough for plain SVG.
 * A text label states the current rhythm, giving a non-visual equivalent of the chart.
 */
import type { MomentumPoint } from "../state/matchState";
import type { Rhythm, RhythmState } from "../types";

const WIDTH = 300;
const HEIGHT = 120;
const MID = HEIGHT / 2;
const MATCH_SAMPLES = 190;

const STATE_LABELS: Record<RhythmState, string> = {
  balanced: "Balanced", home_control: "Home in control", away_control: "Away in control",
  home_pressure: "Home pressing", away_pressure: "Away pressing", chaos: "Chaos",
};

function areaPath(points: MomentumPoint[], sign: 1 | -1): string {
  if (!points.length) return "";
  const step = WIDTH / Math.max(MATCH_SAMPLES, points.length);
  const ys = points.map((p, i) => `${i * step},${MID - sign * Math.max(0, sign * p.momentum) * MID}`);
  return `M0,${MID} L${ys.join(" L")} L${(points.length - 1) * step},${MID} Z`;
}

interface MomentumProps { points: MomentumPoint[]; rhythm: Rhythm | null; homeColor: string; awayColor: string; homeName: string; awayName: string }

export function MomentumChart({ points, rhythm, homeColor, awayColor, homeName, awayName }: MomentumProps) {
  const label = rhythm ? STATE_LABELS[rhythm.state].replace("Home", homeName).replace("Away", awayName) : "Waiting for kick-off";
  return (
    <section className="panel momentum" aria-label="Momentum">
      <h2 className="display">Momentum</h2>
      <p className="rhythm-state" aria-live="polite">{label}</p>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Momentum over time. Current: ${label}`}>
        <line x1={0} y1={MID} x2={WIDTH} y2={MID} stroke="var(--color-border)" strokeDasharray="3 3" />
        <path d={areaPath(points, 1)} fill={homeColor} opacity={0.75} />
        <path d={areaPath(points, -1)} fill={awayColor} opacity={0.75} />
      </svg>
      {rhythm && (
        <p className="muted num" style={{ fontSize: "var(--text-xs)", margin: 0 }}>
          Turnovers {rhythm.turnovers_per_minute.toFixed(1)}/min - {homeName} pass share {Math.round(rhythm.home_pass_share * 100)}%
        </p>
      )}
    </section>
  );
}
