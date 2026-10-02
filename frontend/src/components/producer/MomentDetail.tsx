/**
 * Full broadcast record for one moment: the analyst's reasoning, the commentary, and every audience's overlay.
 * Each overlay shows persona, language, source, latency, and the Standards Editor's verdict with its issues.
 * Held moments can be released to air from here.
 */
import { momentLabel } from "../../lib/labels";
import type { BroadcastRecord } from "../../types";
import { FactCheckBadge, ProvenanceBadge } from "../ProvenanceBadge";

interface DetailProps { record: BroadcastRecord | null; onRelease: (momentId: string) => void }

export function MomentDetail({ record, onRelease }: DetailProps) {
  if (!record) return <p className="muted">Select an aired moment to inspect what each agent produced.</p>;
  return (
    <div className="stack">
      <header className="detail-header">
        <div>
          <span className="muted num">{record.minute} - {momentLabel(record.kind)}</span>
          <h3 className="display" style={{ margin: 0 }}>{record.explanation.headline}</h3>
        </div>
        {record.status === "held" && (
          <button className="button-primary" onClick={() => onRelease(record.moment_id)}>Release to air</button>
        )}
      </header>
      <section aria-label="Analyst reasoning">
        <p style={{ margin: 0 }}>{record.explanation.why_it_matters}</p>
        <ul className="evidence">{record.explanation.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
        <p className="muted" style={{ margin: 0 }}><em>Commentary:</em> {record.commentary}</p>
      </section>
      <table className="cue-table">
        <thead><tr><th>Audience</th><th>Overlay</th><th>Source</th><th>Fact-check</th></tr></thead>
        <tbody>
          {record.cues.map((cue) => (
            <tr key={cue.cue_id}>
              <td>{cue.persona.replace("_", " ")}<br /><span className="muted">{cue.language.toUpperCase()}</span></td>
              <td><strong>{cue.title}</strong><br />{cue.body}</td>
              <td><ProvenanceBadge provenance={cue.provenance.card} /></td>
              <td><FactCheckBadge check={cue.provenance.fact_check} />
                {cue.provenance.fact_check?.verdict === "skipped" && <span className="muted">Template</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
