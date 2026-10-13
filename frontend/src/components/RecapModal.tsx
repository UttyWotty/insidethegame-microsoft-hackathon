/**
 * Dialog presenting the automated half-time or full-time recap written by the Match Editor agent.
 * It keeps keyboard focus inside while open, closes on Escape, the backdrop, or the close button, and returns focus
 * to where the viewer was.
 * Provenance shows whether the recap came from the model or the grounded template.
 */
import { useEffect, useRef } from "react";
import type { PersonaKey, Recap } from "../types";

const PERSONA_NAMES: Record<PersonaKey, string> = {
  analyst: "The Analyst", casual: "The Casual Fan", superfan: "The Superfan", player_tracker: "The Player Tracker",
  newcomer: "The Newcomer",
};

const FOCUSABLE = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

/** Keep Tab and Shift+Tab cycling within the dialog. */
function trapTab(e: KeyboardEvent, dialog: HTMLElement | null): void {
  const items = dialog ? Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

export function RecapModal({ recap, onClose }: { recap: Recap; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const latestClose = useRef(onClose);
  latestClose.current = onClose;
  // Runs once per opening: the parent re-renders on every match event, so depending on onClose would refocus.
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") latestClose.current();
      if (e.key === "Tab") trapTab(e, dialogRef.current);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, []);
  const { recap: r } = recap;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div ref={dialogRef} className="panel modal stack" role="dialog" aria-modal="true" aria-labelledby="recap-title"
        onClick={(e) => e.stopPropagation()}>
        <span className="chip">{recap.stage === "half_time" ? "Half-time recap" : "Full-time recap"} - {recap.source === "fallback" ? "Template" : "AI"}</span>
        {recap.take && (
          <section className="recap-take" aria-label="Your take">
            <span className="term">Your take - {recap.persona ? PERSONA_NAMES[recap.persona] : ""}</span>
            <h2 id="recap-title" className="display" style={{ fontSize: "var(--text-xl)", margin: 0 }}>{recap.take.headline}</h2>
            <p style={{ margin: 0 }}>{recap.take.take}</p>
          </section>
        )}
        <h3 className="display" style={{ margin: 0 }} {...(recap.take ? {} : { id: "recap-title" })}>{r.headline}</h3>
        <p>{r.summary}</p>
        <div><strong>Turning points</strong><ol>{r.turning_points.map((t) => <li key={t}>{t}</li>)}</ol></div>
        <p><strong>Standout player:</strong> {r.standout_player}</p>
        <p className="muted">{r.tactical_story}</p>
        <button ref={closeRef} className="button-primary" onClick={onClose}>Back to the match</button>
      </div>
    </div>
  );
}
