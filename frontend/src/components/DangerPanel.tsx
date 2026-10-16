/**
 * Danger leaderboard: the players whose completed passes and carries have added the most expected threat (xT)
 * so far, from the live snapshot. It uses the same markup and classes as the Physical panel beside it.
 * Nothing renders until at least one player has added positive xT.
 */
import { dangerRows } from "../lib/threat";
import type { MatchMetadata, ThreatLeader } from "../types";

const XT_DECIMALS = 3;

interface DangerPanelProps { leaders: ThreatLeader[] | undefined; match: MatchMetadata; homeColor: string; awayColor: string }

export function DangerPanel({ leaders, match, homeColor, awayColor }: DangerPanelProps) {
  const rows = dangerRows(leaders, match);
  if (!rows.length) return null;
  return (
    <section className="panel stack" aria-label="Danger leaderboard">
      <h2 className="display">Danger</h2>
      <div className="stack" style={{ gap: "var(--space-1)" }}>
        <span className="term">Expected threat (xT) added</span>
        <ol className="leaderboard">
          {rows.map((row) => (
            <li key={row.playerId}>
              <span className="swatch" style={{ background: row.side === "home" ? homeColor : awayColor }} aria-hidden="true" />
              <span className="leader-name">{row.name}</span>
              <span className="num">{row.value.toFixed(XT_DECIMALS)} xT</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
