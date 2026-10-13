/**
 * SVG tactical overlay for the 2D pitch: the defending block with its width and depth, the defending side's
 * offside line, a pressure halo around the ball carrier, and arrows to the carrier's best passing options labelled
 * with their completion chance.
 */
import { PITCH_WIDTH } from "../../lib/pitch";
import { chanceBand, PRESSURE_RADIUS_M, type Tactics } from "../../lib/tactics";

const BAND_COLORS = { safe: "#4ade80", risky: "#fbbf24", unlikely: "#f87171" } as const;
const PERCENT = 100;

export function TacticsLayer({ tactics, homeColor, awayColor }: { tactics: Tactics; homeColor: string; awayColor: string }) {
  const { shapes, offsideX, carrier, options } = tactics;
  return (
    <g className="tactics" pointerEvents="none">
      <defs>
        {Object.entries(BAND_COLORS).map(([band, color]) => (
          <marker key={band} id={`arrow-${band}`} viewBox="0 0 10 10" refX={9} refY={5} markerWidth={4} markerHeight={4}
            orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={color} /></marker>
        ))}
      </defs>
      {(["home", "away"] as const).map((side) => {
        const box = shapes[side];
        if (!box) return null;
        const color = side === "home" ? homeColor : awayColor;
        return (
          <g key={side}>
            <rect x={box.x} y={box.y} width={box.depthM} height={box.widthM} fill={color} fillOpacity={0.06}
              stroke={color} strokeOpacity={0.7} strokeWidth={0.25} strokeDasharray="1 0.8" />
            <text className="tactics-label" x={box.x + 0.5} y={box.y + box.widthM - 0.6}>
              {`Block ${Math.round(box.depthM)} m deep, ${Math.round(box.widthM)} m wide`}
            </text>
          </g>
        );
      })}
      {offsideX !== null && (
        <g>
          <line x1={offsideX} y1={0} x2={offsideX} y2={PITCH_WIDTH} stroke="#facc15" strokeWidth={0.3} strokeDasharray="1.4 0.8" />
          <text className="tactics-label" x={offsideX + 0.6} y={PITCH_WIDTH - 1}>Offside line</text>
        </g>
      )}
      {carrier && carrier.pressers > 0 && (
        <circle cx={carrier.position.x} cy={carrier.position.y} r={PRESSURE_RADIUS_M} fill="#f87171"
          fillOpacity={0.06 + 0.06 * carrier.pressers} stroke="#f87171" strokeWidth={0.25} />
      )}
      {options.map((o) => {
        const band = chanceBand(o.chance);
        return (
          <g key={o.playerId}>
            <line x1={o.from.x} y1={o.from.y} x2={o.to.x} y2={o.to.y} stroke={BAND_COLORS[band]} strokeWidth={0.35}
              markerEnd={`url(#arrow-${band})`} />
            <text className="tactics-label" x={(o.from.x + o.to.x) / 2} y={(o.from.y + o.to.y) / 2 - 0.6} textAnchor="middle">
              {`${Math.round(o.chance * PERCENT)}%`}
            </text>
          </g>
        );
      })}
    </g>
  );
}
