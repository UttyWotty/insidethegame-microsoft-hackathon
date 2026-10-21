/**
 * Pure logic for the expected threat (xT) graphics: the line-breaker card read from a threat_created moment, its
 * stat rows per persona, the danger leaderboard rows, and the analyst-only xT rows of the match stats panel.
 * Display durations are wall-clock milliseconds, so the card reads the same at every replay speed.
 * Values arrive already rounded by the backend, so the graphics only format them.
 */
import { LEADERBOARD_SIZE, type LeaderRow } from "./broadcastStats";
import type { EventUpdate, MatchMetadata, PersonaKey, Snapshot, ThreatLeader } from "../types";

export const THREAT_KIND = "threat_created";
/** How long the line-breaker card stays on screen, in wall-clock milliseconds. */
export const THREAT_CARD_MS = 6000;
const XT_DECIMALS = 3;
const PANEL_XT_DECIMALS = 2;
const LINES_JOINER = " and ";
const UNKNOWN = "-";

/** A line-breaking pass as the broadcast shows it; at is the wall-clock time it arrived. */
export interface ThreatFlash {
  momentId: string; passer: string; receiver: string; side: "home" | "away"; xtAdded: number; xtStart: number;
  xtEnd: number; bypassed: number | null; lines: string; at: number;
}

/** A team comparison row of the stats panel. */
export interface StatRow { label: string; home: number; away: number; format: (v: number) => string }

/** The line-breaking pass carried by an update's threat_created moment, or null when it has none. */
export function threatFlash(update: EventUpdate, homeTeamId: string, at: number): ThreatFlash | null {
  const moment = update.moments.find((m) => m.kind === THREAT_KIND);
  if (!moment) return null;
  const f = moment.facts;
  return {
    momentId: moment.moment_id, passer: String(f.passer ?? ""), receiver: String(f.receiver ?? ""),
    side: moment.team_id === homeTeamId ? "home" : "away", xtAdded: Number(f.xt_added ?? 0),
    xtStart: Number(f.xt_start ?? 0), xtEnd: Number(f.xt_end ?? 0),
    bypassed: typeof f.opponents_bypassed === "number" ? f.opponents_bypassed : null, lines: String(f.lines_broken ?? ""),
    at,
  };
}

/** "midfield and defence" as "Midfield, defence". */
function linesLabel(lines: string): string {
  if (!lines) return UNKNOWN;
  const text = lines.split(LINES_JOINER).join(", ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Stat rows of the line-breaker card: xT rows for the analyst only, bypassed and lines for every persona. */
export function threatCardRows(flash: ThreatFlash, persona: PersonaKey): [string, string][] {
  const shared: [string, string][] = [
    ["Opponents bypassed", flash.bypassed === null ? UNKNOWN : String(flash.bypassed)],
    ["Lines broken", linesLabel(flash.lines)],
  ];
  if (persona !== "analyst") return shared;
  const sign = flash.xtAdded >= 0 ? "+" : "";
  return [
    ["xT added", `${sign}${flash.xtAdded.toFixed(XT_DECIMALS)}`],
    ["xT", `${flash.xtStart.toFixed(XT_DECIMALS)} to ${flash.xtEnd.toFixed(XT_DECIMALS)}`],
    ...shared,
  ];
}

/** Danger leaderboard rows, most xT added first, limited to LEADERBOARD_SIZE; empty when leaders are missing. */
export function dangerRows(leaders: ThreatLeader[] | undefined, match: MatchMetadata): LeaderRow[] {
  if (!leaders) return [];
  return [...leaders]
    .sort((a, b) => b.xt_added - a.xt_added)
    .slice(0, LEADERBOARD_SIZE)
    .map((leader) => ({ playerId: leader.player_id, name: leader.name, value: leader.xt_added,
                        side: leader.team_id === match.home.team_id ? "home" : "away" }));
}

/** Analyst-only rows of the match stats panel: expected threat (xT) and line-breaking passes per team. */
export function analystStatRows(snapshot: Snapshot): StatRow[] {
  const h = snapshot.home.stats, a = snapshot.away.stats;
  return [
    { label: "Expected threat (xT)", home: h.xt_added ?? 0, away: a.xt_added ?? 0,
      format: (v) => v.toFixed(PANEL_XT_DECIMALS) },
    { label: "Line-breaking passes", home: h.line_breaking_passes ?? 0, away: a.line_breaking_passes ?? 0,
      format: (v) => `${Math.round(v)}` },
  ];
}
