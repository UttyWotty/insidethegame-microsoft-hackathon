/**
 * SVG highlight of the zone the Tactical Scout flagged, drawn on the 2D pitch under the players.
 * The band is filled with the beneficiary team's colour, outlined with a dashed line, and labelled with the pattern.
 * Its rectangle comes from lib/scout.ts in the screen frame, so it follows the teams when they change ends.
 */
import type { ZoneRect } from "../../lib/scout";

const LABEL_INSET = 1.2;
const LABEL_BASELINE = 2.6;

export function ScoutZone({ zone, color, label }: { zone: ZoneRect; color: string; label: string }) {
  return (
    <g className="scout-zone" pointerEvents="none">
      <rect x={zone.x} y={zone.y} width={zone.width} height={zone.height} fill={color} fillOpacity={0.16}
        stroke={color} strokeWidth={0.4} strokeDasharray="1.6 1" />
      <text className="scout-zone-label" x={zone.x + LABEL_INSET} y={zone.y + LABEL_BASELINE}>{label}</text>
    </g>
  );
}
