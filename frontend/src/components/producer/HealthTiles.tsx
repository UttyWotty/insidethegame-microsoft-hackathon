/**
 * Pipeline health tiles for the producer: volume, AI share, fact-check outcomes, latency, and audiences.
 * Numbers are shown as text first so they read at a glance in a busy control room.
 * Rates come from cue provenance recorded by the multi-agent pipeline.
 */
import type { ProducerSummary } from "../../types";

const PERCENT = 100;

function share(rates: Record<string, number> | undefined): string {
  if (!rates) return "-";
  const ai = (rates.model ?? 0) + (rates.model_retry ?? 0);
  return `${Math.round(ai * PERCENT)}%`;
}

export function HealthTiles({ summary }: { summary: ProducerSummary }) {
  const { health } = summary;
  const checks = health.fact_checks;
  const tiles = [
    { label: "Moments produced", value: String(health.moments) },
    { label: "Overlays produced", value: String(health.cues) },
    { label: "Cards written by AI", value: share(health.source_rates.card) },
    { label: "Fact-checks passed", value: String((checks.approved ?? 0) + (checks.revised ?? 0)) },
    { label: "Corrected by editor", value: String(checks.revised ?? 0) },
    { label: "Mean card latency", value: `${(health.mean_card_latency_ms / 1000).toFixed(1)}s` },
    { label: "Live audiences", value: String(summary.segments) },
  ];
  return (
    <div className="tiles" role="list" aria-label="Pipeline health">
      {tiles.map((t) => (
        <div className="tile" role="listitem" key={t.label}>
          <span className="tile-value num">{t.value}</span>
          <span className="tile-label">{t.label}</span>
        </div>
      ))}
    </div>
  );
}
