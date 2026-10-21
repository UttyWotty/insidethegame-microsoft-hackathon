/**
 * SVG graphics of an instant replay on the 2D pitch, drawn above the grass and below the players.
 * The build-up path traces the ball's route through the possession, and the shot cone shades the triangle from the
 * shooter to both posts, both in the shooting team's colour. Points arrive in the screen frame from lib/replayAnalysis.ts.
 */
import type { Point } from "../../types";

interface ReplayAnalysisLayerProps {
  /** Shot cone (origin, then both posts), or null while the build-up is still playing. */
  cone: Point[] | null;
  /** Build-up path so far; fewer than two points draws no path. */
  path: Point[];
  color: string;
}

const points = (list: Point[]) => list.map((p) => `${p.x},${p.y}`).join(" ");

export function ReplayAnalysisLayer({ cone, path, color }: ReplayAnalysisLayerProps) {
  return (
    <g className="replay-analysis-layer" pointerEvents="none">
      {cone && <polygon className="replay-cone" points={points(cone)} fill={color} stroke={color} />}
      {path.length > 1 && <polyline className="replay-path" points={points(path)} stroke={color} />}
    </g>
  );
}
