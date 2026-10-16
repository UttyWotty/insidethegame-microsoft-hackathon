/**
 * SVG graphic of a shape shift on the 2D pitch, drawn above the grass and below the players.
 * It shows the team's back line before the shift as a dashed line and now as a solid line, an arrow between them,
 * and the team's current block outline, all in the team's colour, with the block named under the "Now" label.
 * Lines and label spots come from lib/shape.ts in the screen frame, so they follow the teams when they change ends.
 */
import { PITCH_WIDTH } from "../../lib/pitch";
import type { PlayerDot } from "../../lib/playerDots";
import { blockLabel, lineScreenX, type ShapeShiftFlash, SHIFT_ARROW_Y, shiftLabels } from "../../lib/shape";
import { shapeBox } from "../../lib/tactics";

const ARROW_Y = SHIFT_ARROW_Y;
const ARROW_HEAD = 1.4;
const BOX_PAD = 1.5;

export function ShapeShiftLayer({ flash, players, color }: { flash: ShapeShiftFlash; players: PlayerDot[]; color: string }) {
  const isHome = flash.side === "home";
  const before = lineScreenX(flash.lineBeforeM, isHome, flash.period);
  const now = lineScreenX(flash.lineAfterM, isHome, flash.period);
  const towardRight = now > before;
  const box = shapeBox(players, flash.side);
  const labels = shiftLabels(before, now);
  const head = towardRight ? -ARROW_HEAD : ARROW_HEAD;
  return (
    <g className="shape-shift-layer" pointerEvents="none">
      {box && (
        <rect x={box.x - BOX_PAD} y={box.y - BOX_PAD} width={box.depthM + 2 * BOX_PAD} height={box.widthM + 2 * BOX_PAD}
          fill={color} fillOpacity={0.08} stroke={color} strokeWidth={0.35} strokeDasharray="0.9 0.6" />
      )}
      <line x1={before} y1={0} x2={before} y2={PITCH_WIDTH} stroke={color} strokeWidth={0.4} strokeDasharray="1.4 1" />
      <line x1={now} y1={0} x2={now} y2={PITCH_WIDTH} stroke={color} strokeWidth={0.6} />
      <line x1={before} y1={ARROW_Y} x2={now} y2={ARROW_Y} stroke={color} strokeWidth={0.4} />
      <polyline points={`${now + head},${ARROW_Y - ARROW_HEAD} ${now},${ARROW_Y} ${now + head},${ARROW_Y + ARROW_HEAD}`}
        fill="none" stroke={color} strokeWidth={0.4} />
      <text className="shape-shift-label" x={labels.before.x} y={labels.before.y}
        textAnchor={labels.before.anchor}>{`Before ${flash.lineBeforeM} m`}</text>
      <text className="shape-shift-label" x={labels.now.x} y={labels.now.y}
        textAnchor={labels.now.anchor}>{`Now ${flash.lineAfterM} m`}</text>
      <text className="shape-shift-label" x={labels.block.x} y={labels.block.y}
        textAnchor={labels.block.anchor}>{blockLabel(flash.blockAfter)}</text>
    </g>
  );
}
