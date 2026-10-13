/**
 * Live commentary feed mixing agent-written commentary lines with key match events.
 * New items appear at the top and are announced politely to assistive technology; an optional voice toggle reads
 * commentary aloud in the viewer's language. Goals are emphasised with weight and colour, not colour alone.
 */
import type { TickerItem } from "../state/matchState";

interface TickerProps { items: TickerItem[]; voice?: { on: boolean; onToggle: () => void } }

export function CommentaryTicker({ items, voice }: TickerProps) {
  return (
    <section className="panel" aria-label="Commentary">
      <div className="panel-heading">
        <h2 className="display">Commentary</h2>
        {voice && (
          <button className="chip" aria-pressed={voice.on} onClick={voice.onToggle}>
            {voice.on ? "Voice on" : "Voice off"}
          </button>
        )}
      </div>
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
