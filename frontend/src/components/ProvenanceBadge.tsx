/**
 * Small chip showing whether an output came from a model, a self-corrected retry, or a grounded fallback.
 * It makes the multi-agent pipeline's reliability visible to producers and judges.
 * Latency is shown so live-readiness is transparent.
 */
import type { OutputSource, Provenance } from "../types";

const LABELS: Record<OutputSource, string> = { model: "AI", model_retry: "AI (corrected)", fallback: "Template" };

export function ProvenanceBadge({ provenance }: { provenance: Provenance | undefined }) {
  if (!provenance) return null;
  const tone = provenance.source === "fallback" ? "chip--fallback" : "chip--model";
  return (
    <span className={`chip ${tone}`} title={`${provenance.attempts} attempt(s), ${provenance.latency_ms} ms`}>
      {LABELS[provenance.source]} <span className="num">{(provenance.latency_ms / 1000).toFixed(1)}s</span>
    </span>
  );
}
