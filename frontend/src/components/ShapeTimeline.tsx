/**
 * Studio chart of both teams' back-line height per minute across the whole match, from the studio shape payload.
 * A divider marks half-time, with first-half stoppage minutes before it, and each shape shift is marked at its
 * minute in the shifting team's colour.
 * The chart carries a text summary of each team's latest line height and block, so it never relies on colour alone.
 */
import { halfTimeX, timelineAxis, timelinePoints, timelineSummary, timelineX, TIMELINE_MAX_M } from "../lib/shape";
import type { MatchMetadata, ShapeStudio } from "../types";

const WIDTH = 300;
const HEIGHT = 110;
const SECONDS_PER_MINUTE = 60;
const MARK_LABEL_Y = 9;

interface ShapeTimelineProps { shape: ShapeStudio; match: MatchMetadata; homeColor: string; awayColor: string }

export function ShapeTimeline({ shape, match, homeColor, awayColor }: ShapeTimelineProps) {
  const marks = shape.shifts.map((m) => ({ period: m.period, minute: Math.floor(m.match_second / SECONDS_PER_MINUTE) + 1 }));
  const axis = timelineAxis([...shape.timeline, ...marks]);
  const lines = timelinePoints(shape.timeline, WIDTH, HEIGHT, axis);
  const summary = timelineSummary(shape.timeline, match.home.name, match.away.name);
  const half = halfTimeX(WIDTH, axis);
  return (
    <section className="shape-timeline stack" aria-label="Back-line height">
      <span className="term">Back-line height (0 to {TIMELINE_MAX_M} m from own goal)</span>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={summary}>
        <line x1={half} y1={0} x2={half} y2={HEIGHT} stroke="var(--color-border)" strokeDasharray="3 3" />
        {shape.shifts.map((mark, index) => {
          const x = timelineX(marks[index].period, marks[index].minute, WIDTH, axis);
          const color = mark.team_id === match.home.team_id ? homeColor : awayColor;
          return (
            <g key={mark.moment_id}>
              <line x1={x} y1={0} x2={x} y2={HEIGHT} stroke={color} strokeWidth={1.2} />
              <text className="shape-timeline-mark" x={x - 2} y={MARK_LABEL_Y} textAnchor="end">{mark.minute_label}</text>
            </g>
          );
        })}
        {lines.home && <polyline points={lines.home} fill="none" stroke={homeColor} strokeWidth={2} />}
        {lines.away && <polyline points={lines.away} fill="none" stroke={awayColor} strokeWidth={2} />}
      </svg>
      <p className="muted" style={{ margin: 0, fontSize: "var(--text-xs)" }}>{summary}</p>
    </section>
  );
}
