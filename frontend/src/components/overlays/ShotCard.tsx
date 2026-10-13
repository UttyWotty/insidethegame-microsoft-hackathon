/**
 * Broadcast shot card: a goal-mouth graphic showing where the shot went and where the keeper dived, with the
 * result, the shooter, and xG, speed, distance, and angle. It appears on the pitch right after every shot.
 */
import { ballSpot, GOAL_HEIGHT, GOAL_WIDTH, keeperX, MOUTH_MARGIN_TOP, MOUTH_MARGIN_X, resultLabel, shotStats } from "../../lib/shotCard";
import type { ShotCardInfo } from "../../types";

const VIEW_W = GOAL_WIDTH + 2 * MOUTH_MARGIN_X;
const VIEW_H = GOAL_HEIGHT + MOUTH_MARGIN_TOP + 0.3;
const KEEPER_W = 0.7;
const KEEPER_H = 1.8;
const BALL_R = 0.22;

export function ShotCard({ card, shooter, color }: { card: ShotCardInfo; shooter: string; color: string }) {
  const spot = ballSpot(card);
  const keeper = keeperX(card);
  const lineY = MOUTH_MARGIN_TOP + GOAL_HEIGHT;
  return (
    <aside className="glass shot-card" style={{ borderTopColor: color }} aria-label={`Shot card: ${resultLabel(card.result)}, ${shooter}`}>
      <div className="shot-card-head">
        <strong className="display">{resultLabel(card.result)}</strong>
        <span>{shooter}</span>
      </div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="shot-mouth" role="img"
        aria-label={spot ? "Where the shot crossed the goal line" : "Shot blocked before reaching goal"}>
        <line x1={0} y1={lineY} x2={VIEW_W} y2={lineY} stroke="rgba(255,255,255,0.35)" strokeWidth={0.05} />
        <rect x={MOUTH_MARGIN_X} y={MOUTH_MARGIN_TOP} width={GOAL_WIDTH} height={GOAL_HEIGHT} fill="rgba(255,255,255,0.06)"
          stroke="#ffffff" strokeWidth={0.12} />
        {keeper !== null && (
          <rect x={keeper - KEEPER_W / 2} y={lineY - KEEPER_H} width={KEEPER_W} height={KEEPER_H} rx={0.3}
            fill="var(--color-warning)" opacity={0.85} />
        )}
        {spot && <circle cx={spot.x} cy={spot.y} r={BALL_R} fill="#ffffff" stroke={color} strokeWidth={0.08} />}
      </svg>
      <dl className="shot-stats">
        {shotStats(card).map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
    </aside>
  );
}
