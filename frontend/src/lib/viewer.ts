/**
 * Pure helpers that turn partial viewer choices into a complete, valid viewer segment.
 * The superfan defaults to the home club and the player tracker to the home side's number 9.
 * Preferences a persona does not use are cleared so equivalent viewers share one backend segment.
 */
import type { MatchMetadata, PersonaKey, ViewerSettings } from "../types";

const DEFAULT_TRACKED_SHIRT = 9;

export function resolveViewer(viewer: ViewerSettings, match: MatchMetadata | null): ViewerSettings {
  const base = { persona: viewer.persona, language: viewer.language, team: null, player: null };
  if (!match) return base;
  if (viewer.persona === "superfan") {
    const valid = [match.home.team_id, match.away.team_id].includes(viewer.team ?? "");
    return { ...base, team: valid ? viewer.team : match.home.team_id };
  }
  if (viewer.persona === "player_tracker") {
    const players = [...match.home.players, ...match.away.players];
    if (viewer.player && players.some((p) => p.player_id === viewer.player)) return { ...base, player: viewer.player };
    const nine = match.home.players.find((p) => p.shirt_number === DEFAULT_TRACKED_SHIRT) ?? match.home.players[0];
    return { ...base, player: nine?.player_id ?? null };
  }
  return base;
}

/** Default viewer for each persona column in the multiview. */
export function personaViewer(persona: PersonaKey, language: string, match: MatchMetadata | null): ViewerSettings {
  return resolveViewer({ persona, language, team: null, player: null }, match);
}
