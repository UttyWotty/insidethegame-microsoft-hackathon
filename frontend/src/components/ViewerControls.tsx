/**
 * Viewer personalization controls: the five personas, output language, favourite club, and tracked player.
 * Persona cards describe each audience so the choice is self-explanatory.
 * Club and player pickers appear only for the personas that need them.
 */
import type { MatchMetadata, PersonaInfo, PersonaKey, ViewerSettings } from "../types";

interface ViewerProps {
  aiOnline: boolean;
  personas: PersonaInfo[];
  languages: Record<string, string>;
  match: MatchMetadata | null;
  viewer: ViewerSettings;
  onChange: (viewer: ViewerSettings) => void;
}

export function ViewerControls({ aiOnline, personas, languages, match, viewer, onChange }: ViewerProps) {
  const players = match ? [...match.home.players, ...match.away.players] : [];
  const choosePersona = (persona: PersonaKey) => onChange({ ...viewer, persona });
  return (
    <section className="panel stack" aria-label="Your viewing experience">
      <h2 className="display">Your experience</h2>
      <p className="help">
        Your persona changes the overlays on the pitch, which moments you see, Ask the analyst answers, and your
        half-time and full-time take. Play-by-play commentary and match stats are shared by everyone.
      </p>
      <div className="persona-grid" role="group" aria-label="Persona">
        {personas.map((p) => (
          <button key={p.key} type="button" className="persona-card" aria-pressed={viewer.persona === p.key} onClick={() => choosePersona(p.key)}>
            <strong>{p.name}</strong>
            <span>{p.audience}</span>
          </button>
        ))}
      </div>
      <label className="field">Language
        <select value={viewer.language} onChange={(e) => onChange({ ...viewer, language: e.target.value })}
          aria-describedby="language-help">
          {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select>
      </label>
      <p className="help" id="language-help">
        {aiOnline
          ? "Overlays, moment commentary, answers, and your recap take are written in this language by the AI agents."
          : "Translation is done by the AI agents, which are offline in this demo, so text stays in English."}
      </p>
      {viewer.persona === "superfan" && match && (
        <label className="field">Favourite club
          <select value={viewer.team ?? ""} onChange={(e) => onChange({ ...viewer, team: e.target.value })}>
            {[match.home, match.away].map((t) => <option key={t.team_id} value={t.team_id}>{t.name}</option>)}
          </select>
        </label>
      )}
      {viewer.persona === "player_tracker" && match && (
        <label className="field">Tracked player
          <select value={viewer.player ?? ""} onChange={(e) => onChange({ ...viewer, player: e.target.value })}>
            {players.map((p) => <option key={p.player_id} value={p.player_id}>{p.name} (#{p.shirt_number}, {p.position})</option>)}
          </select>
        </label>
      )}
    </section>
  );
}
