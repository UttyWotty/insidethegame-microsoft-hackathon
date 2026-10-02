/**
 * Dialog presenting the automated half-time or full-time recap written by the Match Editor agent.
 * It traps attention with a backdrop, closes on Escape or the close button, and moves focus to the button.
 * Provenance shows whether the recap came from the model or the grounded template.
 */
import { useEffect, useRef } from "react";
import type { Recap } from "../types";

export function RecapModal({ recap, onClose }: { recap: Recap; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const { recap: r } = recap;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="panel modal stack" role="dialog" aria-modal="true" aria-labelledby="recap-title" onClick={(e) => e.stopPropagation()}>
        <span className="chip">{recap.stage === "half_time" ? "Half-time recap" : "Full-time recap"} - {recap.source === "fallback" ? "Template" : "AI"}</span>
        <h2 id="recap-title" className="display" style={{ fontSize: "var(--text-xl)" }}>{r.headline}</h2>
        <p>{r.summary}</p>
        <div><strong>Turning points</strong><ol>{r.turning_points.map((t) => <li key={t}>{t}</li>)}</ol></div>
        <p><strong>Standout player:</strong> {r.standout_player}</p>
        <p className="muted">{r.tactical_story}</p>
        <button ref={closeRef} className="button-primary" onClick={onClose}>Back to the match</button>
      </div>
    </div>
  );
}
