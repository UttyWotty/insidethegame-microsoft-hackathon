/**
 * SVG pitch rendering the synthetic match: markings, all 22 tracked players, the ball, and a trail of recent actions.
 * Players involved in the latest action get live name tags, and the broadcast camera tilts the pitch like a TV angle.
 * The ball's on-screen position is reported to the parent so overlays can anchor to it in either camera mode.
 */
import { useLayoutEffect, useRef, type ReactNode } from "react";
import { PITCH_LENGTH, PITCH_WIDTH } from "../lib/pitch";
import type { TrailPoint } from "../state/matchState";
import type { Point } from "../types";

const STRIPES = 10;
const BALL_RADIUS = 0.9;
const TRAIL_RADIUS = 0.5;
const SHOT_SIZE = 1.3;
const PLAYER_RADIUS = 1.5;
const TAG_OFFSET = 2.6;
const PERCENT = 100;

export interface PlayerDot {
  id: string; number: number; shortName: string; side: "home" | "away"; position: Point;
  goalkeeper: boolean; tagged: boolean; tracked: boolean; tagBelow: boolean;
}

export type BallAnchor = { left: string; top: string } | null;

interface PitchProps {
  ball: Point | null;
  trail: TrailPoint[];
  players: PlayerDot[];
  homeColor: string;
  awayColor: string;
  label: string;
  camera: "broadcast" | "tactical";
  onBallAnchor: (anchor: BallAnchor) => void;
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

function Player({ dot, color }: { dot: PlayerDot; color: string }) {
  const fill = dot.goalkeeper ? "#facc15" : color;
  return (
    <g className="player" style={{ transform: `translate(${dot.position.x}px, ${dot.position.y}px)` }}>
      {dot.tracked && <circle r={PLAYER_RADIUS + 0.9} fill="none" stroke="#ffffff" strokeWidth={0.35} strokeDasharray="0.8 0.5" />}
      <circle r={PLAYER_RADIUS} fill={fill} stroke="#0b1220" strokeWidth={0.3} />
      <text className="player-number" textAnchor="middle" dominantBaseline="central">{dot.number}</text>
      {(dot.tagged || dot.tracked) && (
        <text className="player-tag" y={dot.tagBelow ? TAG_OFFSET + 1.2 : -TAG_OFFSET} textAnchor="middle">
          {dot.shortName}
        </text>
      )}
    </g>
  );
}

export function Pitch({ ball, trail, players, homeColor, awayColor, label, camera, onBallAnchor, children }: PitchProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const ballRef = useRef<SVGCircleElement>(null);

  useLayoutEffect(() => {
    const wrap = wrapRef.current?.getBoundingClientRect();
    const dot = ballRef.current?.getBoundingClientRect();
    if (!wrap || !dot || !wrap.width) return onBallAnchor(null);
    onBallAnchor({
      left: `${((dot.left + dot.width / 2 - wrap.left) / wrap.width) * PERCENT}%`,
      top: `${((dot.top + dot.height / 2 - wrap.top) / wrap.height) * PERCENT}%`,
    });
  }, [ball, camera, onBallAnchor]);

  return (
    <div className={`pitch-wrap cam-${camera}`} ref={wrapRef}>
      <svg className="pitch" viewBox={`0 0 ${PITCH_LENGTH} ${PITCH_WIDTH}`} role="img" aria-label={label}>
        <Markings />
        {trail.length > 1 && (
          <polyline fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth={0.22}
            points={trail.map((p) => `${p.x},${p.y}`).join(" ")} />
        )}
        {trail.map((p, i) => {
          const color = p.side === "home" ? homeColor : awayColor;
          const opacity = 0.25 + (0.6 * (i + 1)) / trail.length;
          return p.type === "shot"
            ? <rect key={p.id} x={p.x - SHOT_SIZE / 2} y={p.y - SHOT_SIZE / 2} width={SHOT_SIZE} height={SHOT_SIZE}
                fill={color} opacity={opacity} transform={`rotate(45 ${p.x} ${p.y})`} />
            : <circle key={p.id} cx={p.x} cy={p.y} r={TRAIL_RADIUS} fill={color} opacity={opacity} />;
        })}
        {players.map((dot) => <Player key={dot.id} dot={dot} color={dot.side === "home" ? homeColor : awayColor} />)}
        {ball && (
          <circle ref={ballRef} className="ball" cx={ball.x} cy={ball.y} r={BALL_RADIUS} fill="#ffffff"
            stroke="#0b1220" strokeWidth={0.25} />
        )}
      </svg>
      <div className="overlay-layer">{children}</div>
    </div>
  );
}
