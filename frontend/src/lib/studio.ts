/**
 * Pure geometry and wording for the studio analysis visuals.
 * Grids become pitch rectangles in metres, pass networks get node and link sizes from pass counts, and space
 * control is summarised in a pundit-style sentence. Everything is in the absolute home frame (home attacks right).
 */
import type { SpaceControl, StudioVisual } from "../types";
import { PITCH_LENGTH, PITCH_WIDTH } from "./pitch";

export const VISUAL_LABELS: Record<StudioVisual, string> = {
  heat_map: "Heat map", pressing: "Pressing map", pass_network: "Pass network", space_control: "Space control",
};
export const VISUALS: StudioVisual[] = ["space_control", "pass_network", "heat_map", "pressing"];
const NODE_MIN_RADIUS = 1.4;
const NODE_SCALE = 0.12;
const NODE_MAX_RADIUS = 4;
const LINK_MIN_WIDTH = 0.2;
const LINK_SCALE = 0.08;
const LINK_MAX_WIDTH = 1.6;
const THIRD_NAMES = ["defensive", "middle", "attacking"] as const;
/** Warm heat scale from pale yellow (few actions) to red (most), readable on the green pitch. */
const HEAT_LOW = [253, 224, 71];
const HEAT_HIGH = [239, 68, 68];
const HEAT_MIN_OPACITY = 0.3;
const HEAT_OPACITY_RANGE = 0.55;

/** A grid cell as a rectangle on the pitch with its value. */
export interface CellRect { x: number; y: number; w: number; h: number; value: number }

/** Rectangles for a rows x columns grid spanning the pitch. */
export function cellRects(grid: number[][]): CellRect[] {
  const rows = grid.length;
  const cols = rows ? grid[0].length : 0;
  const w = PITCH_LENGTH / Math.max(cols, 1);
  const h = PITCH_WIDTH / Math.max(rows, 1);
  return grid.flatMap((line, r) => line.map((value, c) => ({ x: c * w, y: r * h, w, h, value })));
}

/** Radius of a pass network node for the passes a player made. */
export function nodeRadius(passes: number): number {
  return Math.min(NODE_MIN_RADIUS + passes * NODE_SCALE, NODE_MAX_RADIUS);
}

/** Stroke width of a pass network link for the passes between two players. */
export function linkWidth(passes: number): number {
  return Math.min(LINK_MIN_WIDTH + passes * LINK_SCALE, LINK_MAX_WIDTH);
}

/** A pundit-style summary of space control from the home side's view. */
export function describeControl(control: SpaceControl, homeName: string, awayName: string): string {
  const leader = control.home_share >= 50 ? homeName : awayName;
  const share = control.home_share >= 50 ? control.home_share : 100 - control.home_share;
  const best = control.home_thirds.indexOf(Math.max(...control.home_thirds));
  return `${leader} control ${share.toFixed(0)}% of the pitch right now; ${homeName} own most of their `
    + `${THIRD_NAMES[best]} third (${control.home_thirds[best].toFixed(0)}%).`;
}

/** Fill colour and opacity for a heat or pressing cell with a 0..1 value. */
export function heatFill(value: number): { color: string; opacity: number } {
  const t = Math.min(Math.max(value, 0), 1);
  const [r, g, b] = HEAT_LOW.map((low, i) => Math.round(low + (HEAT_HIGH[i] - low) * t));
  return { color: `rgb(${r}, ${g}, ${b})`, opacity: HEAT_MIN_OPACITY + HEAT_OPACITY_RANGE * t };
}
