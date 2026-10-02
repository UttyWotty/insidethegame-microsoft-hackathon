/**
 * Presentation colours for the fictional clubs, keyed by team id.
 * Colours are chosen to stay distinguishable on the dark pitch and against each other.
 * Unknown teams fall back to neutral tones.
 */
export const TEAM_COLORS: Record<string, string> = {
  brk: "#3B82F6",
  irv: "#F97316",
  kba: "#2DD4BF",
  slr: "#C084FC",
};

const FALLBACK_HOME = "#E2E8F0";
const FALLBACK_AWAY = "#FACC15";

export function teamColor(teamId: string | undefined, isHome: boolean): string {
  return (teamId && TEAM_COLORS[teamId]) || (isHome ? FALLBACK_HOME : FALLBACK_AWAY);
}

export const PERSONA_ORDER = ["analyst", "casual", "superfan", "player_tracker", "newcomer"] as const;
