/**
 * Live trace of the multi-agent workflow for one moment: each agent's bar shows when it ran and for how long,
 * what it produced, and whom it handed off to, so a producer can watch the agents collaborate in real time.
 */
import { formatSeconds, traceBars } from "../../lib/trace";
import type { AgentTraceInfo } from "../../types";

const KIND_LABEL = (kind: string) => kind.replace(/_/g, " ");

export function AgentTrace({ trace }: { trace: AgentTraceInfo | null }) {
  if (!trace) return <p className="muted">Agent traces appear as soon as a moment enters production.</p>;
  const bars = traceBars(trace);
  return (
    <div className="stack">
      <p style={{ margin: 0 }}>
        <strong>{trace.minute} {KIND_LABEL(trace.kind)}</strong>{" "}
        <span className={`chip ${trace.finished ? "" : "chip--live"}`}>
          {trace.finished ? `Done in ${formatSeconds(trace.elapsed_ms)}` : `Agents working, ${formatSeconds(trace.elapsed_ms)}`}
        </span>
      </p>
      <ol className="trace" aria-label="Agent timeline">
        {bars.map((bar) => (
          <li key={bar.executorId} className="trace-row">
            <span className="trace-agent">{bar.agent}</span>
            <span className="trace-track" aria-hidden="true">
              <span className={`trace-bar trace-bar--${bar.status}`}
                style={{ left: `${bar.leftPct}%`, width: `${bar.widthPct}%` }} />
            </span>
            <span className="trace-detail">
              {bar.status === "running" ? "working" : bar.status === "failed" ? "failed" : formatSeconds(bar.durationMs)}
              {bar.note ? ` - ${bar.note}` : ""}
              {bar.handsOffTo.length ? ` -> ${bar.handsOffTo.join(", ")}` : ""}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
