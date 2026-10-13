/**
 * Producer console: the broadcaster's control room view of the multi-agent pipeline for one live match.
 * It shows pipeline health, every detected moment, what each agent produced for each audience, and lets a human
 * producer hold AI overlays for approval and release them, keeping people in control of what goes to air.
 */
import { useState } from "react";
import type { MatchMetadata } from "../../types";
import { MatchBar } from "../MultiView";
import { HealthTiles } from "./HealthTiles";
import { MomentDetail } from "./MomentDetail";
import { MomentTimeline } from "./MomentTimeline";
import { useProducer } from "./useProducer";

interface ConsoleProps { sessionId: string; match: MatchMetadata; language: string }

export function ProducerConsole({ sessionId, match, language }: ConsoleProps) {
  const { summary, error, hold, release } = useProducer(sessionId);
  const [selected, setSelected] = useState<string | null>(null);
  const record = summary?.records.find((r) => r.moment_id === (selected ?? summary.records[0]?.moment_id)) ?? null;
  const heldCount = summary?.records.filter((r) => r.status === "held").length ?? 0;
  return (
    <>
      <MatchBar sessionId={sessionId} language={language} match={match} note="Producer console: audit and control AI overlays." />
      <main id="main" tabIndex={-1} className="producer">
        {error && <p className="error" role="alert">{error}</p>}
        {summary && (
          <>
            <div className="producer-controls">
              <button className={`hold-toggle ${summary.hold ? "is-holding" : ""}`} aria-pressed={summary.hold}
                onClick={() => void hold(!summary.hold)}>
                {summary.hold ? "Holding AI overlays for approval" : "AI overlays airing live"}
              </button>
              <button className="chip" disabled={!heldCount} onClick={() => void release(null)}>
                Release all held ({heldCount})
              </button>
            </div>
            <HealthTiles summary={summary} />
            <div className="producer-grid">
              <section className="panel" aria-label="Moment timeline">
                <h2 className="display">Moments</h2>
                <MomentTimeline entries={summary.timeline} selected={record?.moment_id ?? null} onSelect={setSelected} />
              </section>
              <section className="panel" aria-label="Moment detail">
                <h2 className="display">Broadcast record</h2>
                <MomentDetail record={record} onRelease={(id) => void release(id)} />
              </section>
            </div>
          </>
        )}
      </main>
    </>
  );
}
