/**
 * Broadcast score bug showing both clubs, the score, and the match clock.
 * It sits in the top-left of the pitch like a television graphic.
 * The clock displays added time in the conventional 45+2 format.
 */
import { formatClock } from "../lib/pitch";
import type { MatchEvent, Team } from "../types";

interface ScoreBugProps { home: Team; away: Team; homeColor: string; awayColor: string; lastEvent: MatchEvent | null }

export function ScoreBug({ home, away, homeColor, awayColor, lastEvent }: ScoreBugProps) {
  const score = lastEvent?.score ?? { home: 0, away: 0 };
  const clock = lastEvent ? formatClock(lastEvent.match_second, lastEvent.period) : "0:00";
  return (
    <div className="score-bug" aria-label={`${home.name} ${score.home}, ${away.name} ${score.away}, ${clock}`}>
      <span className="swatch" style={{ background: homeColor }} aria-hidden="true" />
      <span className="team">{home.short_name}</span>
      <span className="score num">{score.home}-{score.away}</span>
      <span className="team">{away.short_name}</span>
      <span className="swatch" style={{ background: awayColor }} aria-hidden="true" />
      <span className="clock num">{clock}</span>
    </div>
  );
}
