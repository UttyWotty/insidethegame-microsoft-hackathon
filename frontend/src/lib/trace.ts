/**
 * Pure layout of a moment's agent trace as a timeline: one bar per agent, positioned by when it started and how
 * long it ran, with the agents it hands off to. Running agents extend to the trace's elapsed time.
 */
import type { AgentTraceInfo, TraceStep } from "../types";

const PERCENT = 100;
const MIN_WIDTH_PCT = 1.5;
const MS_PER_SECOND = 1000;

/** One row of the trace timeline. */
export interface TraceBar {
  executorId: string; agent: string; status: TraceStep["status"]; leftPct: number; widthPct: number;
  durationMs: number; note: string; handsOffTo: string[];
}

/** Bars for every step, scaled to the trace's elapsed time. */
export function traceBars(trace: AgentTraceInfo): TraceBar[] {
  const span = Math.max(trace.elapsed_ms, ...trace.steps.map((s) => s.ended_ms ?? 0), 1);
  const names = Object.fromEntries(trace.steps.map((s) => [s.executor_id, s.agent]));
  return trace.steps.map((s) => {
    const end = s.ended_ms ?? trace.elapsed_ms;
    const durationMs = Math.max(end - s.started_ms, 0);
    return {
      executorId: s.executor_id, agent: s.agent, status: s.status, note: s.note, durationMs,
      leftPct: (s.started_ms / span) * PERCENT,
      widthPct: Math.max((durationMs / span) * PERCENT, MIN_WIDTH_PCT),
      handsOffTo: trace.handoffs.filter(([from]) => from === s.executor_id).map(([, to]) => names[to] ?? to),
    };
  });
}

/** Milliseconds below one second, otherwise seconds with one decimal, for bar labels. */
export function formatSeconds(ms: number): string {
  return ms < MS_PER_SECOND ? `${Math.round(ms)} ms` : `${(ms / MS_PER_SECOND).toFixed(1)} s`;
}
