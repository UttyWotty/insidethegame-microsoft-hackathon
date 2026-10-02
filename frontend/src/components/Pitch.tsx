/**
 * SVG pitch that renders the synthetic match feed: markings, the ball, and a trail of recent actions.
 * It is the visual stand-in for broadcast video, with overlays layered on top by the parent.
 * Trail dots use team colours plus distinct shapes for shots so meaning never relies on colour alone.
 */
import type { ReactNode } from "react";
import { PITCH_LENGTH, PITCH_WIDTH } from "../lib/pitch";
import type { TrailPoint } from "../state/matchState";
import type { Point } from "../types";

const STRIPES = 10;
const BALL_RADIUS = 1.1;
const TRAIL_RADIUS = 0.6;
const SHOT_SIZE = 1.4;

interface PitchProps {
  ball: Point | null;
  trail: TrailPoint[];
  homeColor: string;
  awayColor: string;
  label: string;
  children?: ReactNode;
}

function Markings() {
  const stripeWidth = PITCH_LENGTH / STRIPES;
  return (
    <g>
      {Array.from({ length: STRIPES }, (_, i) => (
        <rect key={i} x={i * stripeWidth} y={0} width={stripeWidth} height={PITCH_WIDTH}
          fill={i % 2 ? "var(--color-pitch-stripe)" : "var(--color-pitch)"} />
      ))}
      <g fill="none" stroke="var(--color-pitch-line)" strokeWidth={0.3}>
        <rect x={0.5} y={0.5} width={PITCH_LENGTH - 1} height={PITCH_WIDTH - 1} />
        <line x1={PITCH_LENGTH / 2} y1={0.5} x2={PITCH_LENGTH / 2} y2={PITCH_WIDTH - 0.5} />
        <circle cx={PITCH_LENGTH / 2} cy={PITCH_WIDTH / 2} r={9.15} />
        <rect x={0.5} y={13.84} width={16.5} height={40.32} />
        <rect x={PITCH_LENGTH - 17} y={13.84} width={16.5} height={40.32} />
        <rect x={0.5} y={24.84} width={5.5} height={18.32} />
        <rect x={PITCH_LENGTH - 6} y={24.84} width={5.5} height={18.32} />
      </g>
    </g>
  );
}

export function Pitch({ ball, trail, homeColor, awayColor, label, children }: PitchProps) {
  return (
    <div className="pitch-wrap">
      <svg className="pitch" viewBox={`0 0 ${PITCH_LENGTH} ${PITCH_WIDTH}`} role="img" aria-label={label}>
        <Markings />
        {trail.length > 1 && (
          <polyline fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth={0.25}
            points={trail.map((p) => `${p.x},${p.y}`).join(" ")} />
        )}
        {trail.map((p, i) => {
          const color = p.side === "home" ? homeColor : awayColor;
          const opacity = 0.3 + (0.7 * (i + 1)) / trail.length;
          return p.type === "shot"
            ? <rect key={p.id} x={p.x - SHOT_SIZE / 2} y={p.y - SHOT_SIZE / 2} width={SHOT_SIZE} height={SHOT_SIZE}
                fill={color} opacity={opacity} transform={`rotate(45 ${p.x} ${p.y})`} />
            : <circle key={p.id} cx={p.x} cy={p.y} r={TRAIL_RADIUS} fill={color} opacity={opacity} />;
        })}
        {ball && (
          <circle cx={ball.x} cy={ball.y} r={BALL_RADIUS} fill="#ffffff" stroke="#0b1220" strokeWidth={0.3}
            style={{ transition: "cx 280ms ease-out, cy 280ms ease-out" }} />
        )}
      </svg>
      <div className="overlay-layer">{children}</div>
    </div>
  );
}
