/**
 * Pure logic for the Tactical Scout graphics: reading a flag from a tactical_pattern moment, the flagged zone as a
 * rectangle in the screen frame, the Scout card text, and the payoff line for a goal that fulfils an earlier flag.
 * Zones arrive in the beneficiary team's own frame (right is high y) and are mirrored with toScreen like events.
 * Display durations are wall-clock milliseconds, so the graphics read the same at every replay speed.
 */
import { PITCH_LENGTH, PITCH_WIDTH, toScreen } from "./pitch";
import type { KeyMoment } from "../types";

export const TACTICAL_KIND = "tactical_pattern";
/** How long the Scout card stays on screen after a flag, in wall-clock milliseconds. */
export const SCOUT_CARD_MS = 8000;
/** How long the flagged zone stays highlighted on the pitch, in wall-clock milliseconds. */
export const SCOUT_ZONE_MS = 15000;
const CHANNEL_WIDTH = PITCH_WIDTH / 3;
const THIRD_LENGTH = PITCH_LENGTH / 3;
const CHANNEL_INDEX: Record<string, number> = { left: 0, centre: 1, right: 2 };
const THIRD_INDEX: Record<string, number> = { defensive: 0, middle: 1, final: 2 };
const PATTERN_TITLES: Record<string, string> = {
  flank_exposed: "Flank exposed", channel_overload: "Channel overload", turnover_zone: "Turnover zone",
};

/** A flag as the broadcast shows it; at is the wall-clock time it arrived. */
export interface ScoutFlag {
  momentId: string; minute: string; pattern: string; summary: string; teamId: string; channel: string; third: string;
  count: number; sharePct: number; period: number; at: number;
}

/** A rectangle in the screen frame, in metres. */
export interface ZoneRect { x: number; y: number; width: number; height: number }

/** A flagged zone ready to draw: its rectangle, the beneficiary team's colour, and a short label. */
export interface ScoutZoneInfo { zone: ZoneRect; color: string; label: string }

/** The text of the Scout card. */
export interface ScoutCardText { kicker: string; headline: string; summary: string; stat: string; minute: string }

/** The flag carried by a tactical_pattern moment, or null for any other moment. */
export function scoutFlagFrom(moment: KeyMoment, minute: string, at: number): ScoutFlag | null {
  if (moment.kind !== TACTICAL_KIND || !moment.team_id) return null;
  const f = moment.facts;
  return {
    momentId: moment.moment_id, minute, pattern: String(f.pattern ?? ""), summary: String(f.summary ?? ""),
    teamId: moment.team_id, channel: String(f.channel ?? ""), third: String(f.third ?? ""),
    count: Number(f.count ?? 0), sharePct: Number(f.share_pct ?? 0), period: moment.period, at,
  };
}

/** The flagged zone in the screen frame, from the zone in the team's own attacking frame. */
export function zoneRect(channel: string, third: string, teamIsHome: boolean, period: number): ZoneRect {
  const x0 = (THIRD_INDEX[third] ?? 0) * THIRD_LENGTH;
  const y0 = (CHANNEL_INDEX[channel] ?? 0) * CHANNEL_WIDTH;
  const a = toScreen({ x: x0, y: y0 }, teamIsHome, period);
  const b = toScreen({ x: x0 + THIRD_LENGTH, y: y0 + CHANNEL_WIDTH }, teamIsHome, period);
  return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) };
}

/** Whether something that appeared at `at` is still visible at `now` for a duration in milliseconds. */
export function stillVisible(at: number, now: number, durationMs: number): boolean {
  return now - at < durationMs;
}

/** Kicker, headline, summary, the count and share stat, and the minute for the Scout card. */
export function scoutCardText(flag: ScoutFlag): ScoutCardText {
  const unit = flag.pattern === "turnover_zone" ? "ball wins" : "entries";
  return {
    kicker: "TACTICAL SCOUT", headline: PATTERN_TITLES[flag.pattern] ?? flag.pattern.replace(/_/g, " "),
    summary: flag.summary, stat: `${flag.count} ${unit}, ${flag.sharePct}%`, minute: flag.minute,
  };
}

/** "Scout flagged 38': ..." for a goal linked to an earlier flag, or null when the goal has no flagged minute. */
export function goalPayoffLabel(facts: KeyMoment["facts"]): string | null {
  if (!facts.flagged_minute) return null;
  return `Scout flagged ${String(facts.flagged_minute)}: ${String(facts.flagged_summary ?? "")}`;
}

/** The flagged zone to draw for a flag, coloured for the team that benefits from it. */
export function scoutZoneFor(flag: ScoutFlag, homeTeamId: string, homeColor: string, awayColor: string): ScoutZoneInfo {
  const isHome = flag.teamId === homeTeamId;
  return { zone: zoneRect(flag.channel, flag.third, isHome, flag.period), color: isHome ? homeColor : awayColor,
           label: scoutCardText(flag).headline };
}
