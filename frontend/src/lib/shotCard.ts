/**
 * Pure geometry and labels for the broadcast shot card: the goal mouth drawn as seen from the shooter, with the
 * ball where the shot went and the goalkeeper where they dived, plus the headline stats.
 */
import type { ShotCardInfo } from "../types";

export const GOAL_WIDTH = 7.32;
export const GOAL_HEIGHT = 2.44;
/** Space drawn around the goal frame so wide and high misses stay visible, in metres. */
export const MOUTH_MARGIN_X = 2.6;
export const MOUTH_MARGIN_TOP = 1.4;
const RESULT_LABELS: Record<string, string> = { goal: "GOAL", saved: "SAVED", off_target: "OFF TARGET", blocked: "BLOCKED" };

/** Card drawing coordinates: x from the left of the margin, y downward from the top of the margin, in metres. */
export interface MouthPoint { x: number; y: number }

/** Where the ball crossed the goal line in card coordinates, or null for blocked shots. */
export function ballSpot(card: ShotCardInfo): MouthPoint | null {
  if (card.placement_y === null || card.placement_z === null) return null;
  return { x: MOUTH_MARGIN_X + GOAL_WIDTH / 2 + card.placement_y, y: MOUTH_MARGIN_TOP + GOAL_HEIGHT - card.placement_z };
}

/** The keeper's position along the line in card coordinates, or null when there is no dive. */
export function keeperX(card: ShotCardInfo): number | null {
  return card.keeper_y === null ? null : MOUTH_MARGIN_X + GOAL_WIDTH / 2 + card.keeper_y;
}

/** Headline label for the result. */
export function resultLabel(result: string): string {
  return RESULT_LABELS[result] ?? result.toUpperCase();
}

/** The stat rows shown beside the goal mouth. */
export function shotStats(card: ShotCardInfo): [string, string][] {
  const rows: [string, string][] = [["xG", card.xg.toFixed(2)], ["Distance", `${card.distance_m.toFixed(0)} m`],
    ["Angle", `${card.angle_deg.toFixed(0)} deg`]];
  if (card.speed_kmh !== null) rows.splice(1, 0, ["Speed", `${card.speed_kmh.toFixed(0)} km/h`]);
  return rows;
}
