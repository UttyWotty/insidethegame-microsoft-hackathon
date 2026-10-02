/**
 * Multiview: the same live match seen by all five personas at once, one column each.
 * It demonstrates that one stream of match intelligence becomes five genuinely different experiences.
 * Each column holds its own personalized stream connection.
 */
import { useMatchStream } from "../api/useMatchStream";
import { formatClock, minuteLabel } from "../lib/pitch";
import { PERSONA_ORDER, teamColor } from "../lib/teams";
import { personaViewer } from "../lib/viewer";
import type { MatchMetadata, PersonaInfo, PersonaKey } from "../types";
import { FactCheckBadge, ProvenanceBadge } from "./ProvenanceBadge";

interface ColumnProps { sessionId: string; persona: PersonaKey; info: PersonaInfo | undefined; language: string; match: MatchMetadata }

function PersonaColumn({ sessionId, persona, info, language, match }: ColumnProps) {
  const viewer = personaViewer(persona, language, match);
  const [state] = useMatchStream(sessionId, viewer);
  const focus = viewer.team
    ? [match.home, match.away].find((t) => t.team_id === viewer.team)?.name
    : viewer.player ? [...match.home.players, ...match.away.players].find((p) => p.player_id === viewer.player)?.name : null;
  return (
    <section className="mv-column" aria-label={info?.name ?? persona}>
      <header>
        <h2 className="display" style={{ margin: 0 }}>{info?.name ?? persona}</h2>
        <p className="muted" style={{ margin: 0, fontSize: "var(--text-xs)" }}>{focus ? `Following ${focus}` : info?.voice}</p>
      </header>
      {state.cues.length === 0 && <p className="muted">Waiting for the first moment...</p>}
      {state.cues.map(({ cue }) => (
        <article className="cue-card" key={cue.cue_id}>
          <span className="muted num" style={{ fontSize: "var(--text-xs)" }}>{minuteLabel(cue.display_from_s, cue.period)}</span>
          <h3>{cue.title}</h3>
          <p>{cue.body}</p>
          {cue.stat_callouts.length > 0 && (
            <p className="num muted">{cue.stat_callouts.map((c) => `${c.label}: ${c.value}`).join(" | ")}</p>
          )}
          <ProvenanceBadge provenance={cue.provenance.card} />
          <FactCheckBadge check={cue.provenance.fact_check} />
        </article>
      ))}
    </section>
  );
}

interface MultiViewProps { sessionId: string; personas: PersonaInfo[]; language: string; match: MatchMetadata }

function MatchBar({ sessionId, language, match }: { sessionId: string; language: string; match: MatchMetadata }) {
  const [state, status] = useMatchStream(sessionId, personaViewer("analyst", language, match));
  const event = state.lastEvent;
  const score = event?.score ?? { home: 0, away: 0 };
  return (
    <div className="mv-bar" aria-live="off">
      <span className="team" style={{ borderColor: teamColor(match.home.team_id, true) }}>{match.home.name}</span>
      <span className="score num display">{score.home}-{score.away}</span>
      <span className="team" style={{ borderColor: teamColor(match.away.team_id, false) }}>{match.away.name}</span>
      <span className="num muted">{event ? formatClock(event.match_second, event.period) : "0:00"}</span>
      {state.ended ? <span className="chip">FULL TIME</span> : status === "open" && <span className="chip chip--live">LIVE</span>}
      <span className="muted">Same match, five audiences. Each column is a separately personalized stream.</span>
    </div>
  );
}

export function MultiView({ sessionId, personas, language, match }: MultiViewProps) {
  return (
    <>
    <MatchBar sessionId={sessionId} language={language} match={match} />
    <div className="multiview">
      {PERSONA_ORDER.map((key) => (
        <PersonaColumn key={key} sessionId={sessionId} persona={key} info={personas.find((p) => p.key === key)}
          language={language} match={match} />
      ))}
    </div>
    </>
  );
}
