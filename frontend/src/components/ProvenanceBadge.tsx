/**
 * Small chip showing whether an output came from a model, a self-corrected retry, or a grounded fallback.
 * It makes the multi-agent pipeline's reliability visible to producers and judges.
 * Latency is shown so live-readiness is transparent.
 */
import type { FactCheck, OutputSource, Provenance } from "../types";

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

const CHECK_LABELS: Record<FactCheck["verdict"], string | null> = {
  approved: "Fact-checked", revised: "Corrected by editor", replaced: "Replaced after check", skipped: null,
};

/** Chip showing what the Standards Editor agent did with an output; issues appear as a tooltip. */
export function FactCheckBadge({ check }: { check: FactCheck | undefined }) {
  const label = check ? CHECK_LABELS[check.verdict] : null;
  if (!check || !label) return null;
  return <span className="chip chip--check" title={check.issues.join("; ") || "No issues found"}>{label}</span>;
}
