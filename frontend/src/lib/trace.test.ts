/**
 * Tests for the agent trace timeline layout.
 * They check bar positions, running bars, minimum widths, and handoff labels.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { formatSeconds, traceBars } from "./trace";
import type { AgentTraceInfo } from "../types";

const trace: AgentTraceInfo = {
  moment_id: "m", minute: "23'", kind: "goal", finished: false, elapsed_ms: 4000, handoffs: [["intake", "analyst"]],
  steps: [
    { executor_id: "intake", agent: "Intake", status: "done", started_ms: 0, ended_ms: 10, note: "1 audience" },
    { executor_id: "analyst", agent: "Match Analyst", status: "running", started_ms: 1000, ended_ms: null, note: "" },
  ],
};

describe("traceBars", () => {
  it("positions bars by start and duration, extending running agents to now", () => {
    const [intake, analyst] = traceBars(trace);
    expect(intake.leftPct).toBe(0);
    expect(intake.widthPct).toBe(1.5);
    expect(intake.handsOffTo).toEqual(["Match Analyst"]);
    expect(analyst).toMatchObject({ leftPct: 25, widthPct: 75, durationMs: 3000, status: "running" });
    expect(formatSeconds(analyst.durationMs)).toBe("3.0 s");
    expect(formatSeconds(16)).toBe("16 ms");
  });
});
