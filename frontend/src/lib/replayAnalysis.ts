/**
 * Pure labels and geometry for the instant replay's analysis overlay: what the card says and where the pitch draws.
 * The analyst gets the full set of shot facts, while every other persona gets a plain-language subset.
 * Cone and build-up points arrive in the absolute home frame and are converted to the screen frame for the period.
 */
import type { PersonaKey, Point, ReplayAnalysis, ReplayKeyframe } from "../types";
import { toScreen } from "./pitch";
import { resultLabel, shotStats } from "./shotCard";

const XT_DIGITS = 3;
/** Replay xG decimals: the model value goal chance is computed from, so "xG 0.075" sits beside "Goal chance 8%". */
const REPLAY_XG_DIGITS = 3;
const DURATION_DIGITS = 0;
/** Event type of the keyframe where a pass reaches its receiver; it adds no point to the build-up path. */
export const RECEPTION_EVENT = "reception";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(XT_DIGITS)}`;
}

function nameOf(id: string, names: Record<string, string>): string {
  return names[id] ?? id;
}

/** The value of one shot-card stat row (xG, Speed, Distance, Angle), or null when the card does not have it. */
function cardStat(a: ReplayAnalysis, label: string): string | null {
  return shotStats(a.card).find(([key]) => key === label)?.[1] ?? null;
}

/** The replay's xG at REPLAY_XG_DIGITS decimals, the same value goal_chance_pct is rounded from. */
export function replayXg(a: ReplayAnalysis): string {
  return a.xg.toFixed(REPLAY_XG_DIGITS);
}

/** Build-up summary, for example "6 passes in 31 s". */
export function buildUpLabel(a: ReplayAnalysis): string {
  return `${plural(a.build_up.passes, "pass", "passes")} in ${a.build_up.duration_s.toFixed(DURATION_DIGITS)} s`;
}

/**
 * The assist in full, for example "Name, 34 m, xT +0.019", plus ", broke the defence line, 5 bypassed" when it broke
 * a line; null when the shooter received no pass. The xT part is left out when no threat was stored.
 */
export function assistLabel(a: ReplayAnalysis, names: Record<string, string>): string | null {
  const assist = a.assist;
  if (!assist) return null;
  const parts = [nameOf(assist.passer_id, names), `${assist.length_m.toFixed(0)} m`];
  if (assist.xt_added !== null) parts.push(`xT ${signed(assist.xt_added)}`);
  if (assist.breaks_line) {
    parts.push(`broke the ${assist.lines_broken.join(" and ")} line`);
    if (assist.opponents_bypassed !== null) parts.push(`${assist.opponents_bypassed} bypassed`);
  }
  return parts.join(", ");
}

function coneLabel(a: ReplayAnalysis): string {
  return `${plural(a.defenders_in_cone, "defender", "defenders")}, ${a.keeper_in_cone ? "keeper" : "no keeper"}`;
}

function analystRows(a: ReplayAnalysis, names: Record<string, string>): [string, string][] {
  const rows: [string, string][] = [["Result", resultLabel(a.card.result)], ["xG", replayXg(a)],
    ["Goal chance", `${a.goal_chance_pct}%`], ["Distance", cardStat(a, "Distance") ?? ""],
    ["Angle", cardStat(a, "Angle") ?? ""]];
  const speed = cardStat(a, "Speed");
  if (speed !== null) rows.push(["Speed", speed]);
  rows.push(["In the cone", coneLabel(a)], ["Pressure", a.under_pressure ? "Under pressure" : "Unpressured"],
    ["Build-up", buildUpLabel(a)], ["xT built", signed(a.build_up.xt_added)]);
  const assist = assistLabel(a, names);
  if (assist !== null) rows.push(["Assist", assist]);
  return rows;
}

function plainRows(a: ReplayAnalysis, names: Record<string, string>): [string, string][] {
  const rows: [string, string][] = [["Goal chance", `${a.goal_chance_pct}%`],
    ["Distance", cardStat(a, "Distance") ?? ""]];
  const speed = cardStat(a, "Speed");
  if (speed !== null) rows.push(["Speed", speed]);
  rows.push(["Build-up", plural(a.build_up.passes, "pass", "passes")]);
  if (a.assist) rows.push(["Assist", nameOf(a.assist.passer_id, names)]);
  return rows;
}

/** The analysis card rows for a persona: the full set for the analyst, a plain-language subset for everyone else. */
export function analysisRows(a: ReplayAnalysis, persona: PersonaKey, names: Record<string, string>): [string, string][] {
  return persona === "analyst" ? analystRows(a, names) : plainRows(a, names);
}

/** The shot cone (origin and both posts) in the screen frame for the period. */
export function coneScreen(a: ReplayAnalysis, period: number): Point[] {
  return a.cone.map(([x, y]) => toScreen({ x, y }, true, period));
}

/**
 * The build-up path point of keyframe index: one point per action keyframe so far, so a reception keyframe keeps
 * its pass's point (pass to pathScreen as upTo).
 */
export function pathIndex(frames: ReplayKeyframe[], index: number): number {
  return frames.slice(0, index + 1).filter((f) => f.event_type !== RECEPTION_EVENT).length - 1;
}

/** The build-up path's first upTo + 1 points (keyframe ball points, then the shot origin) in the screen frame. */
export function pathScreen(a: ReplayAnalysis, period: number, upTo: number): Point[] {
  return a.build_up.path.slice(0, Math.max(upTo, 0) + 1).map(([x, y]) => toScreen({ x, y }, true, period));
}
