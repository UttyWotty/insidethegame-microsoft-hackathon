/**
 * Presentation colours for the fictional clubs, keyed by team id.
 * Colours are chosen to stay distinguishable against each other and reach 3:1 contrast on both pitch stripes.
 * Unknown teams fall back to neutral tones.
 */
export const TEAM_COLORS: Record<string, string> = {
  brk: "#7DB4FB",
  irv: "#FB923C",
  kba: "#2DD4BF",
  slr: "#D0A2FD",
};

const FALLBACK_HOME = "#E2E8F0";
const FALLBACK_AWAY = "#FACC15";

export function teamColor(teamId: string | undefined, isHome: boolean): string {
  return (teamId && TEAM_COLORS[teamId]) || (isHome ? FALLBACK_HOME : FALLBACK_AWAY);
}

export const PERSONA_ORDER = ["analyst", "casual", "superfan", "player_tracker", "newcomer"] as const;
