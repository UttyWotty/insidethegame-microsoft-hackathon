/**
 * Timeline of every key moment the analytics detected, with importance and whether it went to air.
 * Moments still with the agents show as in production; moments that were not aired stay visible so producers
 * can see what the pacing policy filtered out.
 * Selecting a moment opens its full broadcast record.
 */
import { momentLabel } from "../../lib/labels";
import type { TimelineEntry } from "../../types";

const STATUS_LABELS: Record<string, string> = {
  aired: "Aired", held: "Held", released: "Released", in_production: "In production", not_aired: "Not aired",
};
const PERCENT = 100;

interface TimelineProps { entries: TimelineEntry[]; selected: string | null; onSelect: (id: string) => void }

export function MomentTimeline({ entries, selected, onSelect }: TimelineProps) {
  if (!entries.length) return <p className="muted">Key moments will appear here as the match unfolds.</p>;
  return (
    <ol className="timeline">
      {[...entries].reverse().map((e) => (
        <li key={e.moment_id}>
          <button className="timeline-row" aria-pressed={selected === e.moment_id} onClick={() => onSelect(e.moment_id)}
            disabled={e.status === "not_aired" || e.status === "in_production"}>
            <span className="minute num">{e.minute}</span>
            <span className="kind">{momentLabel(e.kind)}</span>
            <span className="importance" aria-label={`Importance ${Math.round(e.importance * PERCENT)}`}>
              <span style={{ width: `${e.importance * PERCENT}%` }} />
            </span>
            <span className={`chip status-${e.status}`}>{STATUS_LABELS[e.status] ?? e.status}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
