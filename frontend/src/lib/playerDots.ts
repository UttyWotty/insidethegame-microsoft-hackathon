/**
 * Pure conversion of tracked positions into the dots the pitch draws, with name tags and sprint speeds.
 * Shared by the live broadcast and the highlights replay so both tag the players in the action the same way.
 * Players without a position are left out.
 */
import type { MatchMetadata, Point } from "../types";

/** One player as the pitch draws it. */
export interface PlayerDot {
  id: string; number: number; shortName: string; side: "home" | "away"; position: Point;
  goalkeeper: boolean; tagged: boolean; tracked: boolean;
  /** True for the receiver of the latest action, whose tag goes below the dot when there is room. */
  tagBelow: boolean;
  /** Speed in km/h while this player is the recent sprinter, otherwise null. */
  sprintKmh: number | null;
  /** Short event pop-up over the player (for example TACKLE WON), otherwise null. */
  popup: string | null;
}

/** Who is in the action: the actor and receiver get name tags, the receiver's tag sits below. */
export interface ActionFocus { actor: string | null; receiver: string | null }

const NO_POPUP = (): string | null => null;

/**
 * Dots for both teams; tracked is the followed player, sprintFor gives a player's speed tag (or null), and
 * popupFor (default none) gives a player's event pop-up.
 */
export function playerDots(match: MatchMetadata | undefined, positions: Record<string, Point>, focus: ActionFocus,
                           tracked: string | null, sprintFor: (playerId: string) => number | null,
                           popupFor: (playerId: string) => string | null = NO_POPUP): PlayerDot[] {
  if (!match) return [];
  const tagged = new Set([focus.actor, focus.receiver].filter(Boolean));
  return [match.home, match.away].flatMap((team, i) => team.players
    .filter((p) => positions[p.player_id])
    .map((p) => ({
      id: p.player_id, number: p.shirt_number, shortName: p.name.split(" ").slice(-1)[0],
      side: i === 0 ? "home" as const : "away" as const, position: positions[p.player_id],
      goalkeeper: p.position === "GK", tagged: tagged.has(p.player_id), tracked: p.player_id === tracked,
      tagBelow: p.player_id === focus.receiver, sprintKmh: sprintFor(p.player_id), popup: popupFor(p.player_id),
    })));
}
