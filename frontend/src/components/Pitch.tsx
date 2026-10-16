/**
 * SVG pitch rendering the synthetic match: markings, all 22 tracked players, the ball, and a trail of recent actions.
 * Players glide between tracking frames over the real time between events, players involved in the latest action
 * get live name tags, a sprinting player shows their speed, and the broadcast camera tilts the pitch like a TV angle.
 * The ball's on-screen position is reported to the parent so overlays can anchor to it in either camera mode, and
 * a shape shift draws the team's back line before and now with its block, under the players.
 */
import { useLayoutEffect, useRef, type CSSProperties, type ReactNode } from "react";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M, RUNOFF_TOP_M, tagPlacement } from "../lib/pitch";
import type { PlayerDot } from "../lib/playerDots";
import type { ScoutZoneInfo } from "../lib/scout";
import type { ShapeShiftFlash } from "../lib/shape";
import type { Tactics } from "../lib/tactics";
import { ScoutZone } from "./overlays/ScoutZone";
import { ShapeShiftLayer } from "./overlays/ShapeShiftLayer";
import { TacticsLayer } from "./overlays/TacticsLayer";

export type { PlayerDot } from "../lib/playerDots";
import type { ShotTrace, TrailPoint } from "../state/matchState";
import type { Point } from "../types";

const STRIPES = 10;
const BALL_RADIUS = 0.9;
const TRAIL_RADIUS = 0.5;
const SHOT_SIZE = 1.3;
const PLAYER_RADIUS = 1.5;
const TAG_OFFSET = 2.6;
const SPEED_OFFSET = 4.6;
const BELOW_EXTRA = 1.2;
/** Sideways shift of a tag anchored at its start or end, so it begins beside the dot rather than at its centre. */
const ANCHOR_SHIFT: Record<"start" | "middle" | "end", number> = { start: -PLAYER_RADIUS, middle: 0, end: PLAYER_RADIUS };
const PERCENT = 100;
const XG_BUBBLE_MIN = 1.2;
const XG_BUBBLE_SCALE = 6;
const SHOT_RESULTS: Record<string, string> = { goal: "GOAL", saved: "Saved", off_target: "Wide", blocked: "Blocked" };


export type BallAnchor = { left: string; top: string } | null;

interface PitchProps {
  ball: Point | null;
  trail: TrailPoint[];
  players: PlayerDot[];
  /** Milliseconds players take to glide to their latest positions. */
  moveMs: number;
  homeColor: string;
  awayColor: string;
  label: string;
  camera: "broadcast" | "tactical";
  shot: ShotTrace | null;
  onBallAnchor: (anchor: BallAnchor) => void;
  children?: ReactNode;
  /** Replay crop as x, y, width, height in metres; null (default) shows the whole pitch. */
  zoom?: [number, number, number, number] | null;
  /** Tactical overlay (lines, shapes, pressure, passing options); null (default) draws none. */
  tactics?: Tactics | null;
  /** Zone flagged by the Tactical Scout, drawn under the players; null (default) draws none. */
  scoutZone?: ScoutZoneInfo | null;
  /** Shape shift to draw (back line before and now, block outline); null (default) draws none. */
  shapeShift?: ShapeShiftFlash | null;
}

export function Markings() {
  const stripeWidth = PITCH_LENGTH / STRIPES;
  return (
    <g>
      <rect x={-RUNOFF_M} y={-RUNOFF_TOP_M} width={PITCH_LENGTH + 2 * RUNOFF_M}
        height={PITCH_WIDTH + RUNOFF_TOP_M + RUNOFF_M}
        fill="var(--color-pitch-runoff)" />
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
  const place = tagPlacement(dot.position, dot.tagBelow);
  const tagX = ANCHOR_SHIFT[place.anchor];
  return (
    <g className="player" style={{ transform: `translate(${dot.position.x}px, ${dot.position.y}px)` }}>
      {dot.tracked && <circle r={PLAYER_RADIUS + 0.9} fill="none" stroke="#ffffff" strokeWidth={0.35} strokeDasharray="0.8 0.5" />}
      <circle r={PLAYER_RADIUS} fill={fill} stroke="#0b1220" strokeWidth={0.3} />
      <text className="player-number" textAnchor="middle" dominantBaseline="central">{dot.number}</text>
      {(dot.tagged || dot.tracked || dot.sprintKmh !== null || dot.popup) && (
        <text className="player-tag" x={tagX} y={place.below ? TAG_OFFSET + BELOW_EXTRA : -TAG_OFFSET}
          textAnchor={place.anchor}>
          {dot.shortName}
        </text>
      )}
      {dot.popup && (
        <text className="player-popup" y={place.below ? SPEED_OFFSET + BELOW_EXTRA + 2 : -SPEED_OFFSET - (dot.sprintKmh !== null ? 2 : 0)}
          x={tagX} textAnchor={place.anchor}>{dot.popup}</text>
      )}
      {dot.sprintKmh !== null && (
        <text className="player-speed" x={tagX} y={place.below ? SPEED_OFFSET + BELOW_EXTRA : -SPEED_OFFSET}
          textAnchor={place.anchor}>
          {`${dot.sprintKmh.toFixed(1)} km/h`}
        </text>
      )}
    </g>
  );
}

function Shot({ shot, color }: { shot: ShotTrace; color: string }) {
  const radius = XG_BUBBLE_MIN + (shot.xg ?? 0) * XG_BUBBLE_SCALE;
  return (
    <g className="shot-trace" key={shot.id}>
      <line x1={shot.from.x} y1={shot.from.y} x2={shot.to.x} y2={shot.to.y} stroke={color} strokeWidth={0.45}
        strokeDasharray="1.2 0.8" />
      <circle cx={shot.from.x} cy={shot.from.y} r={radius} fill={color} fillOpacity={0.25} stroke={color} strokeWidth={0.3} />
      {shot.xg !== null && (
        <text className="shot-label" x={shot.from.x} y={shot.from.y - radius - 0.8} textAnchor="middle">xG {shot.xg.toFixed(2)}</text>
      )}
      <text className="shot-label" x={shot.to.x} y={shot.to.y - 1.5} textAnchor="middle">{SHOT_RESULTS[shot.result] ?? ""}</text>
    </g>
  );
}

export function Pitch({ ball, trail, players, moveMs, homeColor, awayColor, label, camera, shot, onBallAnchor,
                       children, zoom = null, tactics = null, scoutZone = null, shapeShift = null }: PitchProps) {
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
      <svg className="pitch" role="img" aria-label={label}
        viewBox={zoom ? zoom.join(" ")
          : `${-RUNOFF_M} ${-RUNOFF_TOP_M} ${PITCH_LENGTH + 2 * RUNOFF_M} ${PITCH_WIDTH + RUNOFF_TOP_M + RUNOFF_M}`}
        style={{ "--move-ms": `${moveMs}ms` } as CSSProperties}>
        <Markings />
        {scoutZone && <ScoutZone zone={scoutZone.zone} color={scoutZone.color} label={scoutZone.label} />}
        {shapeShift && <ShapeShiftLayer flash={shapeShift} players={players}
          color={shapeShift.side === "home" ? homeColor : awayColor} />}
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
        {tactics && <TacticsLayer tactics={tactics} homeColor={homeColor} awayColor={awayColor} />}
        {shot && <Shot shot={shot} color={shot.side === "home" ? homeColor : awayColor} />}
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
