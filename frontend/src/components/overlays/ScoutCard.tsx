/**
 * Tactical Scout card: a glass broadcast card that appears when the Scout flags a pattern in the event stream.
 * It shows the kicker, the pattern, the summary sentence, the count and share that prove it, and the minute.
 * It sits bottom-right, clear of the score bug, the shot card and stat panel, and the lower third's left edge.
 */
import type { CSSProperties } from "react";
import { scoutCardText, type ScoutFlag } from "../../lib/scout";

export function ScoutCard({ flag, color }: { flag: ScoutFlag; color: string }) {
  const text = scoutCardText(flag);
  return (
    <aside className="glass scout-card" style={{ "--team-color": color } as CSSProperties}
      aria-label={`Tactical Scout: ${text.headline}. ${text.summary}`}>
      <div className="scout-card-head">
        <span className="scout-kicker">{text.kicker}</span>
        <span className="num">{text.minute}</span>
      </div>
      <strong className="display scout-headline">{text.headline}</strong>
      <p className="scout-summary">{text.summary}</p>
      <span className="scout-stat num">{text.stat}</span>
    </aside>
  );
}
