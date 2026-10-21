/**
 * Side-by-side team comparison bars for possession, shots, xG, passing, and pressing.
 * Values come from the live snapshot so they update as the match unfolds.
 * Each row shows numbers as text as well as bars, so it never relies on colour alone; analysts also get expected
 * threat (xT), line-breaking pass, back-line height, and block rows.
 */
import { shapeStatRows } from "../lib/shape";
import { analystStatRows, type StatRow } from "../lib/threat";
import type { PersonaKey, Snapshot } from "../types";

type Row = StatRow;

const pct = (v: number) => `${Math.round(v)}%`;
const int = (v: number) => `${Math.round(v)}`;
const dec = (v: number) => v.toFixed(2);
const ratioPct = (v: number) => `${Math.round(v * 100)}%`;

function rows(snapshot: Snapshot): Row[] {
  const h = snapshot.home.stats, a = snapshot.away.stats;
  return [
    { label: "Possession", home: snapshot.home.possession_pct, away: snapshot.away.possession_pct, format: pct },
    { label: "Shots", home: h.shots, away: a.shots, format: int },
    { label: "On target", home: h.shots_on_target, away: a.shots_on_target, format: int },
    { label: "Expected goals (xG)", home: h.xg, away: a.xg, format: dec },
    { label: "Pass accuracy", home: h.pass_accuracy, away: a.pass_accuracy, format: ratioPct },
    { label: "Final third entries", home: h.final_third_entries, away: a.final_third_entries, format: int },
    { label: "Pressures", home: h.pressures, away: a.pressures, format: int },
  ];
}

interface StatsPanelProps { snapshot: Snapshot | null; homeColor: string; awayColor: string; persona?: PersonaKey }

export function StatsPanel({ snapshot, homeColor, awayColor, persona }: StatsPanelProps) {
  if (!snapshot) return <section className="panel"><h2 className="display">Match stats</h2><p className="muted">Waiting for kick-off</p></section>;
  const extra = persona === "analyst" ? [...analystStatRows(snapshot), ...shapeStatRows(snapshot)] : [];
  return (
    <section className="panel stack" aria-label="Match statistics">
      <h2 className="display">Match stats</h2>
      {[...rows(snapshot), ...extra].map((row) => {
        const total = row.home + row.away || 1;
        return (
          <div className="stat-row" key={row.label}>
            <span className="label">{row.label}</span>
            <span className="num">{row.format(row.home)}</span>
            <div className="stat-bar" aria-hidden="true">
              <span style={{ width: `${(row.home / total) * 100}%`, background: homeColor }} />
              <span style={{ width: `${(row.away / total) * 100}%`, background: awayColor }} />
            </div>
            <span className="num" style={{ textAlign: "right" }}>{row.format(row.away)}</span>
          </div>
        );
      })}
    </section>
  );
}
