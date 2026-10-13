/**
 * Broadcast score bug showing both clubs, the score, the match clock, and a live win probability bar beneath.
 * It sits in the top-left of the pitch like a television graphic.
 * The clock displays added time in the conventional 45+2 format.
 */
import { winPercentages } from "../lib/broadcastStats";
import { formatClock } from "../lib/pitch";
import type { MatchEvent, Team, WinProbability } from "../types";

interface ScoreBugProps {
  home: Team; away: Team; homeColor: string; awayColor: string; lastEvent: MatchEvent | null;
  /** Live win probability; null (default) hides the bar. */
  win?: WinProbability | null;
}

function WinBar({ win, home, away, homeColor, awayColor }:
  { win: WinProbability; home: Team; away: Team; homeColor: string; awayColor: string }) {
  const pct = winPercentages(win);
  return (
    <div className="win-bar" role="img"
      aria-label={`Win probability: ${home.short_name} ${pct.home}%, draw ${pct.draw}%, ${away.short_name} ${pct.away}%`}>
      <span style={{ width: `${pct.home}%`, background: homeColor }}>{pct.home >= 12 ? `${pct.home}%` : ""}</span>
      <span className="win-draw" style={{ width: `${pct.draw}%` }}>{pct.draw >= 12 ? `${pct.draw}%` : ""}</span>
      <span style={{ width: `${pct.away}%`, background: awayColor }}>{pct.away >= 12 ? `${pct.away}%` : ""}</span>
    </div>
  );
}

export function ScoreBug({ home, away, homeColor, awayColor, lastEvent, win = null }: ScoreBugProps) {
  const score = lastEvent?.score ?? { home: 0, away: 0 };
  const clock = lastEvent ? formatClock(lastEvent.match_second, lastEvent.period) : "0:00";
  return (
    <div className="score-stack">
    <div className="score-bug" aria-label={`${home.name} ${score.home}, ${away.name} ${score.away}, ${clock}`}>
      <span className="swatch" style={{ background: homeColor }} aria-hidden="true" />
      <span className="team">{home.short_name}</span>
      <span className="score num">{score.home}-{score.away}</span>
      <span className="team">{away.short_name}</span>
      <span className="swatch" style={{ background: awayColor }} aria-hidden="true" />
      <span className="clock num">{clock}</span>
    </div>
    {win && <WinBar win={win} home={home} away={away} homeColor={homeColor} awayColor={awayColor} />}
    </div>
  );
}
