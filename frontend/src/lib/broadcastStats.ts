/**
 * Pure helpers for live broadcast stat graphics: win probability segments for the score bug, short event pop-ups
 * over the player who made the action, and the distance and top-speed leaderboards.
 */
import type { MatchEvent, MatchMetadata, PhysicalStats, WinProbability } from "../types";

/** How long an event pop-up stays over the player. */
export const POPUP_MS = 1800;
/** How many players each leaderboard lists. */
export const LEADERBOARD_SIZE = 5;
const PERCENT = 100;
const POPUPS: Record<string, string> = { tackle: "TACKLE WON", interception: "INTERCEPTION", save: "SAVE" };

/** Whole-number percentages for the win bar that always add up to 100. */
export function winPercentages(win: WinProbability): { home: number; draw: number; away: number } {
  const home = Math.round(win.home * PERCENT);
  const away = Math.round(win.away * PERCENT);
  return { home, draw: Math.max(PERCENT - home - away, 0), away };
}

/** The pop-up for the latest event (player and text), or null when it has expired or the event earns none. */
export function eventPopup(event: MatchEvent | null, arrivedAt: number | null, now: number):
  { playerId: string; text: string } | null {
  if (!event || !event.player_id || arrivedAt === null || now - arrivedAt > POPUP_MS) return null;
  const text = POPUPS[event.event_type];
  if (!text || (event.event_type === "tackle" && event.outcome !== "success")) return null;
  return { playerId: event.player_id, text };
}

/** A leaderboard row. */
export interface LeaderRow { playerId: string; name: string; side: "home" | "away"; value: number }

/** Top players by a physical stat, highest first. */
export function leaderboard(physical: PhysicalStats, match: MatchMetadata, stat: "distance_km" | "top_kmh"): LeaderRow[] {
  const sides = new Map<string, { side: "home" | "away"; name: string }>();
  match.home.players.forEach((p) => sides.set(p.player_id, { side: "home", name: p.name }));
  match.away.players.forEach((p) => sides.set(p.player_id, { side: "away", name: p.name }));
  return Object.entries(physical)
    .flatMap(([id, v]) => {
      const who = sides.get(id);
      return who ? [{ playerId: id, name: who.name, side: who.side, value: v[stat] }] : [];
    })
    .sort((a, b) => b.value - a.value)
    .slice(0, LEADERBOARD_SIZE);
}
