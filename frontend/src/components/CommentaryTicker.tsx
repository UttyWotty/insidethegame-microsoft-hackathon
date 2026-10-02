/**
 * Live commentary feed mixing agent-written commentary lines with key match events.
 * New items appear at the top and are announced politely to assistive technology.
 * Goals are emphasised with weight and colour, not colour alone.
 */
import type { TickerItem } from "../state/matchState";

export function CommentaryTicker({ items }: { items: TickerItem[] }) {
  return (
    <section className="panel" aria-label="Commentary">
      <h2 className="display">Commentary</h2>
      {items.length === 0 ? <p className="muted">Commentary will appear here.</p> : (
        <ol className="ticker" aria-live="polite">
          {items.map((item) => (
            <li key={item.id}>
              <span className="minute num">{item.minute}</span>
              <span className={item.tone}>{item.text}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
