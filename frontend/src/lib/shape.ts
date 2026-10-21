/**
 * Pure logic for the team-shape graphics: the shape-shift flash read from a shape_shift moment and back-line heights
 * placed in the screen frame.
 * It also draws the studio line-height timeline as SVG polylines with a text summary, and the analyst-only back-line
 * and block rows of the match stats panel.
 * Line heights arrive in metres from each team's own goal line, already rounded by the backend.
 */
import { PITCH_WIDTH, toScreen } from "./pitch";
import type { StatRow } from "./threat";
import type { Block, EventUpdate, ShapeTimelinePoint, Snapshot } from "../types";

export const SHAPE_SHIFT_KIND = "shape_shift";
/** How long the shape-shift lines stay on the pitch, in wall-clock milliseconds. */
export const SHAPE_SHIFT_MS = 12000;
/** Back-line heights at or above this are a high block (mirrors the backend's HIGH_BLOCK_MIN_M). */
export const HIGH_BLOCK_MIN_M = 33;
/** Back-line heights below this are a low block (mirrors the backend's LOW_BLOCK_MAX_M). */
export const LOW_BLOCK_MAX_M = 24;
/** Top of the timeline's vertical scale, in metres from the own goal line. */
export const TIMELINE_MAX_M = 50;
const BLOCK_RANK: Record<Block, number> = { low: 1, mid: 2, high: 3 };
const RANK_BLOCK: Record<number, Block> = { 1: "low", 2: "mid", 3: "high" };
const SHAPE_DECIMALS = 1;
/** Regulation minutes per half: second-half minutes are numbered from HALF_MINUTES + 1 whatever the stoppage. */
export const HALF_MINUTES = 45;
/** The half-time divider sits this far after the last first-half minute on the timeline. */
const HALF_TIME_GAP = 0.5;
/** Pitch-frame y of the shift arrow, the vertical middle of the pitch. */
export const SHIFT_ARROW_Y = PITCH_WIDTH / 2;
/** Labels sit just below the arrow, clear of the top-right shot card and the bottom "Offside line" label. */
const SHIFT_LABEL_DROP = 2.6;
/** Vertical step from the "Now" label to the block label stacked under it. */
const SHIFT_LABEL_STEP = 2.4;
/** Horizontal gap between a line and its label. */
const SHIFT_LABEL_GAP = 0.8;

/** A shape shift as the broadcast shows it; at is the wall-clock time it arrived. */
export interface ShapeShiftFlash {
  momentId: string; teamId: string; side: "home" | "away"; period: number; lineBeforeM: number; lineAfterM: number;
  blockAfter: Block; at: number;
}

/** One SVG text position in the pitch frame. */
export interface LabelSpot { x: number; y: number; anchor: "start" | "end" }

/** Where the shape-shift layer writes its "Before", "Now", and block labels. */
export interface ShiftLabels { before: LabelSpot; now: LabelSpot; block: LabelSpot }

/** The timeline's x scale: first-half minutes run to firstHalfEnd, second-half minutes follow, up to maxSlot. */
export interface TimelineAxis { firstHalfEnd: number; maxSlot: number }

/** The two timeline series as SVG polyline point lists. */
export interface TimelineLines { home: string; away: string }

/** The block label for a back-line height, using the backend's thresholds. */
export function blockFor(lineM: number): Block {
  if (lineM >= HIGH_BLOCK_MIN_M) return "high";
  return lineM < LOW_BLOCK_MAX_M ? "low" : "mid";
}

/** "Low block" from "low". */
export function blockLabel(block: Block): string {
  return `${block.charAt(0).toUpperCase()}${block.slice(1)} block`;
}

/** The shift carried by an update's shape_shift moment, or null when it has none. */
export function shapeShiftFlash(update: EventUpdate, homeTeamId: string, at: number): ShapeShiftFlash | null {
  const moment = update.moments.find((m) => m.kind === SHAPE_SHIFT_KIND);
  if (!moment || !moment.team_id) return null;
  const f = moment.facts;
  const lineAfterM = Number(f.line_after_m ?? 0);
  const block = String(f.block_after ?? "");
  return {
    momentId: moment.moment_id, teamId: moment.team_id, side: moment.team_id === homeTeamId ? "home" : "away",
    period: moment.period, lineBeforeM: Number(f.line_before_m ?? 0), lineAfterM,
    blockAfter: block in BLOCK_RANK ? (block as Block) : blockFor(lineAfterM), at,
  };
}

/** Screen x of a team's back line at lineM metres from its own goal line, in a period (teams change ends). */
export function lineScreenX(lineM: number, teamIsHome: boolean, period: number): number {
  return toScreen({ x: lineM, y: 0 }, teamIsHome, period).x;
}

/** Horizontal position of a minute on a timeline that runs from minute 1 at x 0 to maxMinute at x width. */
export function minuteX(minute: number, width: number, maxMinute: number): number {
  const span = Math.max(maxMinute - 1, 1);
  return ((Math.min(minute, maxMinute) - 1) / span) * width;
}

/**
 * Label spots for a shift from the before line to the now line (screen x): both just below the mid-pitch arrow, each
 * on the outside of its line, with the block label stacked under "Now". The band stays clear of the top-right shot
 * card and of the tactics "Offside line" label at the bottom edge.
 */
export function shiftLabels(before: number, now: number): ShiftLabels {
  const towardRight = now > before;
  const y = SHIFT_ARROW_Y + SHIFT_LABEL_DROP;
  const nowSpot: LabelSpot = { x: now + (towardRight ? SHIFT_LABEL_GAP : -SHIFT_LABEL_GAP), y,
                               anchor: towardRight ? "start" : "end" };
  return {
    before: { x: before + (towardRight ? -SHIFT_LABEL_GAP : SHIFT_LABEL_GAP), y, anchor: towardRight ? "end" : "start" },
    now: nowSpot,
    block: { ...nowSpot, y: y + SHIFT_LABEL_STEP },
  };
}

/** The axis for timeline marks: first-half stoppage minutes stay before half-time and push the second half along. */
export function timelineAxis(marks: { period: number; minute: number }[]): TimelineAxis {
  const firstHalfEnd = Math.max(HALF_MINUTES, ...marks.filter((m) => m.period <= 1).map((m) => m.minute));
  const lastSlot = Math.max(0, ...marks.map((m) => timelineSlot(m.period, m.minute, firstHalfEnd)));
  return { firstHalfEnd, maxSlot: Math.max(firstHalfEnd + HALF_MINUTES, lastSlot) };
}

/** A minute's slot on the axis: first-half minutes as they are, second-half minutes after the first half's end. */
export function timelineSlot(period: number, minute: number, firstHalfEnd: number): number {
  return period <= 1 ? minute : minute - HALF_MINUTES + firstHalfEnd;
}

/** Period-aware horizontal position of a minute on a timeline of the given width. */
export function timelineX(period: number, minute: number, width: number, axis: TimelineAxis): number {
  return minuteX(timelineSlot(period, minute, axis.firstHalfEnd), width, axis.maxSlot);
}

/** Horizontal position of the half-time divider, between the first half's last minute and the second half. */
export function halfTimeX(width: number, axis: TimelineAxis): number {
  return minuteX(axis.firstHalfEnd + HALF_TIME_GAP, width, axis.maxSlot);
}

function lineY(lineM: number, height: number): number {
  return height - (Math.min(Math.max(lineM, 0), TIMELINE_MAX_M) / TIMELINE_MAX_M) * height;
}

function series(points: ShapeTimelinePoint[], pick: (p: ShapeTimelinePoint) => number | null, width: number,
                height: number, axis: TimelineAxis): string {
  return points
    .filter((p) => pick(p) !== null)
    .map((p) => `${timelineX(p.period, p.minute, width, axis).toFixed(SHAPE_DECIMALS)},${lineY(pick(p) as number, height).toFixed(SHAPE_DECIMALS)}`)
    .join(" ");
}

/** Home and away back-line heights as polyline point lists, period-aware, skipping minutes without a reading. */
export function timelinePoints(points: ShapeTimelinePoint[], width: number, height: number,
                               axis: TimelineAxis): TimelineLines {
  return {
    home: series(points, (p) => p.home_line_m, width, height, axis),
    away: series(points, (p) => p.away_line_m, width, height, axis),
  };
}

function latest(points: ShapeTimelinePoint[], pick: (p: ShapeTimelinePoint) => number | null): number | null {
  for (let i = points.length - 1; i >= 0; i -= 1) {
    const value = pick(points[i]);
    if (value !== null) return value;
  }
  return null;
}

/** A sentence naming each team's latest back-line height and block, the text equivalent of the timeline. */
export function timelineSummary(points: ShapeTimelinePoint[], homeName: string, awayName: string): string {
  const parts = ([[homeName, latest(points, (p) => p.home_line_m)], [awayName, latest(points, (p) => p.away_line_m)]] as
    [string, number | null][])
    .filter(([, line]) => line !== null)
    .map(([name, line]) => `${name} ${(line as number).toFixed(SHAPE_DECIMALS)} m (${blockLabel(blockFor(line as number)).toLowerCase()})`);
  return parts.length ? `Back-line height per minute. Latest: ${parts.join(", ")}.`
    : "Back-line height per minute. Waiting for enough tracking.";
}

/** Analyst-only rows: back-line height and block per team; empty without a snapshot shape or before both readings. */
export function shapeStatRows(snapshot: Snapshot): StatRow[] {
  const home = snapshot.shape?.home, away = snapshot.shape?.away;
  if (!home || !away) return [];
  return [
    { label: "Back line (m)", home: home.line_height_m, away: away.line_height_m,
      format: (v) => v.toFixed(SHAPE_DECIMALS) },
    { label: "Block", home: BLOCK_RANK[home.block], away: BLOCK_RANK[away.block],
      format: (v) => blockLabel(RANK_BLOCK[Math.round(v)] ?? "mid").replace(" block", "") },
  ];
}
