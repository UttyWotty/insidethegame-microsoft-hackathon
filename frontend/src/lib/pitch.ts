/**
 * Pure pitch geometry for rendering: converts team-relative event coordinates into a fixed screen frame.
 * The home side attacks right in the first half and left in the second, as teams change ends at half-time.
 * Coordinates are metres on a 105 x 68 pitch, matching the backend.
 */
import type { MatchEvent, Point } from "../types";

export const PITCH_LENGTH = 105;
export const PITCH_WIDTH = 68;
const SECOND_PERIOD = 2;

/** Whether the acting team's attacking direction must be mirrored to the screen frame. */
export function needsMirror(teamIsHome: boolean, period: number): boolean {
  const homeAttacksRight = period < SECOND_PERIOD;
  return teamIsHome !== homeAttacksRight;
}

/** Convert a team-relative point to the screen frame. */
export function toScreen(point: Point, teamIsHome: boolean, period: number): Point {
  return needsMirror(teamIsHome, period) ? { x: PITCH_LENGTH - point.x, y: PITCH_WIDTH - point.y } : point;
}

/** Where the ball is after an event, in the screen frame, or null when the event has no location. */
export function ballAfter(event: MatchEvent, homeTeamId: string): Point | null {
  const location = event.end ?? event.start;
  if (!location) return null;
  return toScreen(location, event.team_id === homeTeamId, event.period);
}

/** Format a match second as a broadcast clock, showing added time as 45+2 or 90+3. */
export function formatClock(matchSecond: number, period: number): string {
  const periodEndMinute = period === 1 ? 45 : 90;
  const minute = Math.floor(matchSecond / 60);
  const second = Math.floor(matchSecond % 60).toString().padStart(2, "0");
  if (minute >= periodEndMinute) return `${periodEndMinute}+${minute - periodEndMinute + 1}'`;
  return `${minute}:${second}`;
}

/** Broadcast-style minute label for a moment, for example 23', 45+3' or 90+1'. */
export function minuteLabel(matchSecond: number, period: number): string {
  const periodEndMinute = period === 1 ? 45 : 90;
  const minute = Math.floor(matchSecond / 60) + 1;
  return minute > periodEndMinute ? `${periodEndMinute}+${minute - periodEndMinute}'` : `${minute}'`;
}
