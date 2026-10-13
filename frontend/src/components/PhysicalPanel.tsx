/**
 * Physical leaderboard: the players who have covered the most ground and reached the highest speeds so far,
 * from the speed-limited tracking. It updates with each live snapshot.
 */
import { leaderboard } from "../lib/broadcastStats";
import type { MatchMetadata, PhysicalStats } from "../types";

interface PhysicalPanelProps { physical: PhysicalStats | undefined; match: MatchMetadata; homeColor: string; awayColor: string }

export function PhysicalPanel({ physical, match, homeColor, awayColor }: PhysicalPanelProps) {
  if (!physical || !Object.keys(physical).length) return null;
  const boards = [
    { title: "Distance covered", rows: leaderboard(physical, match, "distance_km"), unit: (v: number) => `${v.toFixed(1)} km` },
    { title: "Top speed", rows: leaderboard(physical, match, "top_kmh"), unit: (v: number) => `${v.toFixed(1)} km/h` },
  ];
  return (
    <section className="panel stack" aria-label="Physical leaderboard">
      <h2 className="display">Physical</h2>
      {boards.map((board) => (
        <div key={board.title} className="stack" style={{ gap: "var(--space-1)" }}>
          <span className="term">{board.title}</span>
          <ol className="leaderboard">
            {board.rows.map((row) => (
              <li key={row.playerId}>
                <span className="swatch" style={{ background: row.side === "home" ? homeColor : awayColor }} aria-hidden="true" />
                <span className="leader-name">{row.name}</span>
                <span className="num">{board.unit(row.value)}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}
