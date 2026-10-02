/**
 * "Ask the analyst" panel: viewers question the Match Companion agent about the live match.
 * Answers arrive in the viewer's persona voice and language, with supporting stats and suggested follow-ups.
 * Pending state, errors, and provenance are always visible, and new answers are announced politely.
 */
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { CompanionReply, ViewerSettings } from "../types";
import { ProvenanceBadge } from "./ProvenanceBadge";

const STARTERS = ["Who has been the best player so far?", "Why has the momentum changed?", "Which team is in control?"];
const MAX_QUESTION = 300;

export function AskPanel({ sessionId, viewer }: { sessionId: string; viewer: ViewerSettings }) {
  const [question, setQuestion] = useState("");
  const [replies, setReplies] = useState<CompanionReply[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setError(null);
    try {
      const reply = await api.ask(sessionId, trimmed, viewer);
      setReplies((current) => [reply, ...current]);
      setQuestion("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The companion is unavailable right now.");
    } finally {
      setPending(false);
    }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(question); };
  const suggestions = replies[0]?.follow_ups.length ? replies[0].follow_ups : STARTERS;

  return (
    <section className="panel stack" aria-label="Ask the analyst">
      <h2 className="display">Ask the analyst</h2>
      <form className="ask-form" onSubmit={submit}>
        <label className="visually-hidden" htmlFor="ask-input">Your question about this match</label>
        <input id="ask-input" value={question} maxLength={MAX_QUESTION} placeholder="Ask about this match..."
          onChange={(e) => setQuestion(e.target.value)} disabled={pending} />
        <button className="button-primary" type="submit" disabled={pending || question.trim().length < 3}>
          {pending ? "Thinking..." : "Ask"}
        </button>
      </form>
      <div className="suggestions" role="group" aria-label="Suggested questions">
        {suggestions.map((s) => (
          <button key={s} type="button" className="chip suggestion" onClick={() => void ask(s)} disabled={pending}>{s}</button>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <ol className="answers" aria-live="polite">
        {replies.map((r, i) => (
          <li key={`${r.question}-${replies.length - i}`} className="cue-card">
            <p className="muted" style={{ margin: 0 }}>{r.question}</p>
            <p>{r.answer}</p>
            {r.stat_callouts.length > 0 && <p className="num muted">{r.stat_callouts.map((c) => `${c.label}: ${c.value}`).join(" | ")}</p>}
            <ProvenanceBadge provenance={{ source: r.source, attempts: 1, latency_ms: r.latency_ms }} />
          </li>
        ))}
      </ol>
    </section>
  );
}
