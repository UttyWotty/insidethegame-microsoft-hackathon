/**
 * Studio view for pundit segments: heat maps, pressing maps, pass networks, and space control on the pitch.
 * By default it follows the Match Analyst: the theme of the newest explanation picks the visual, and the
 * explanation sits beside it. Viewers can pick a visual, switch team, or narrow the maps to the last 15 minutes.
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M } from "../lib/pitch";
import { cellRects, describeControl, heatFill, linkWidth, nodeRadius, VISUAL_LABELS, VISUALS } from "../lib/studio";
import { teamColor } from "../lib/teams";
import type { MatchMetadata, SpaceControl, StudioPayload, StudioTeam, StudioVisual } from "../types";
import { MatchBar } from "./MultiView";
import { Markings } from "./Pitch";

const STUDIO_POLL_MS = 4000;
const CONTROL_OPACITY = 0.5;
const DOT_RADIUS = 1.1;
type Side = "home" | "away";

function GridLayer({ grid }: { grid: number[][] }) {
  return <g>{cellRects(grid).filter((c) => c.value > 0).map((c) => {
    const fill = heatFill(c.value);
    return <rect key={`${c.x}-${c.y}`} x={c.x} y={c.y} width={c.w} height={c.h} fill={fill.color} opacity={fill.opacity} />;
  })}</g>;
}

function NetworkLayer({ team, match, side, color }: { team: StudioTeam; match: MatchMetadata; side: Side; color: string }) {
  const squad = side === "home" ? match.home.players : match.away.players;
  const at = Object.fromEntries(team.network.nodes.map((n) => [n.player_id, n]));
  return (
    <g>
      {team.network.links.map(([a, b, n]) => at[a] && at[b] && (
        <line key={`${a}-${b}`} x1={at[a].x} y1={at[a].y} x2={at[b].x} y2={at[b].y} stroke="#ffffff"
          strokeOpacity={0.75} strokeWidth={linkWidth(n)} strokeLinecap="round" />
      ))}
      {team.network.nodes.map((n) => (
        <g key={n.player_id} transform={`translate(${n.x} ${n.y})`}>
          <circle r={nodeRadius(n.passes)} fill={color} stroke="#0b1220" strokeWidth={0.3} />
          <text className="player-number" textAnchor="middle" dominantBaseline="central">
            {squad.find((p) => p.player_id === n.player_id)?.shirt_number ?? ""}
          </text>
        </g>
      ))}
    </g>
  );
}

function ControlLayer({ control, match, homeColor, awayColor }:
  { control: SpaceControl; match: MatchMetadata; homeColor: string; awayColor: string }) {
  const home = new Set(match.home.players.map((p) => p.player_id));
  return (
    <g>
      {cellRects(control.owners).map((c) => (
        <rect key={`${c.x}-${c.y}`} x={c.x} y={c.y} width={c.w} height={c.h} fill={c.value > 0 ? homeColor : awayColor}
          opacity={CONTROL_OPACITY} />
      ))}
      {(control.positions ?? []).map(([id, x, y]) => (
        <circle key={id} cx={x} cy={y} r={DOT_RADIUS} fill={home.has(id) ? homeColor : awayColor} stroke="#0b1220"
          strokeWidth={0.35} />
      ))}
    </g>
  );
}

export function StudioView({ sessionId, match, language }: { sessionId: string; match: MatchMetadata; language: string }) {
  const [data, setData] = useState<StudioPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const [picked, setPicked] = useState<StudioVisual>("space_control");
  const [side, setSide] = useState<Side>("home");
  const [span, setSpan] = useState<StudioPayload["window"]>("match");

  useEffect(() => {
    let live = true;
    const load = () => api.studio(sessionId, span).then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Studio unavailable"));
    void load();
    const id = window.setInterval(load, STUDIO_POLL_MS);
    return () => { live = false; window.clearInterval(id); };
  }, [sessionId, span]);

  const bar = <MatchBar sessionId={sessionId} language={language} match={match}
    note="Studio: the analyst's reasoning, drawn on the pitch." />;
  if (error || !data) {
    return <>{bar}<main id="main" tabIndex={-1} className="studio-page">
      <div className="panel empty" role={error ? "alert" : undefined}>{error ?? "Preparing the studio..."}</div>
    </main></>;
  }
  const visual = follow ? data.recommended : picked;
  const homeColor = teamColor(match.home.team_id, true);
  const awayColor = teamColor(match.away.team_id, false);
  const team = data.teams[side];
  const color = side === "home" ? homeColor : awayColor;
  const teamName = side === "home" ? match.home.name : match.away.name;
  const caption = visual === "space_control"
    ? (data.control ? describeControl(data.control, match.home.name, match.away.name) : "Waiting for kick-off.")
    : `${VISUAL_LABELS[visual]} for ${teamName}, ${span === "match" ? "whole match" : "last 15 minutes"}.`;

  return (
    <>{bar}<main id="main" tabIndex={-1} className="studio-page"><div className="studio">
      <section className="stack" aria-label="Studio analysis">
        <div className="studio-controls">
          <div className="tabs" role="group" aria-label="Visual">
            {VISUALS.map((v) => (
              <button key={v} className="tab" aria-pressed={visual === v} onClick={() => { setFollow(false); setPicked(v); }}>
                {VISUAL_LABELS[v]}
              </button>
            ))}
          </div>
          <button className="tab" aria-pressed={follow} onClick={() => setFollow((f) => !f)}>Follow the Analyst</button>
          {visual !== "space_control" && (
            <div className="tabs" role="group" aria-label="Team">
              {(["home", "away"] as Side[]).map((s) => (
                <button key={s} className="tab" aria-pressed={side === s} onClick={() => setSide(s)}>
                  {s === "home" ? match.home.short_name : match.away.short_name}
                </button>
              ))}
            </div>
          )}
          <div className="tabs" role="group" aria-label="Time window">
            {(["match", "last_15"] as const).map((w) => (
              <button key={w} className="tab" aria-pressed={span === w} onClick={() => setSpan(w)}>
                {w === "match" ? "Whole match" : "Last 15 min"}
              </button>
            ))}
          </div>
        </div>
        <div className="pitch-wrap cam-tactical">
          <svg className="pitch" role="img" aria-label={`${VISUAL_LABELS[visual]}. ${caption}`}
            viewBox={`${-RUNOFF_M} ${-RUNOFF_M} ${PITCH_LENGTH + 2 * RUNOFF_M} ${PITCH_WIDTH + 2 * RUNOFF_M}`}>
            <Markings />
            {visual === "heat_map" && <GridLayer grid={team.heat} />}
            {visual === "pressing" && <GridLayer grid={team.pressing} />}
            {visual === "pass_network" && <NetworkLayer team={team} match={match} side={side} color={color} />}
            {visual === "space_control" && data.control
              && <ControlLayer control={data.control} match={match} homeColor={homeColor} awayColor={awayColor} />}
          </svg>
        </div>
        <p className="studio-caption">{caption} <span className="muted">{match.home.short_name} attack left to right.</span></p>
      </section>
      <aside className="panel stack studio-analyst" aria-label="The Analyst">
        <span className="term">The Analyst{data.analyst ? ` - ${data.analyst.minute}` : ""}</span>
        {data.analyst ? (
          <>
            <h2 className="display studio-headline">{data.analyst.headline}</h2>
            <p style={{ margin: 0 }}>{data.analyst.why_it_matters}</p>
            <div className="studio-chips">
              <span className="chip">{data.analyst.theme.replace("_", " ")}</span>
              <span className="chip">{data.analyst.source === "agent" ? "AI" : "Template"}</span>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Recommended visual: {VISUAL_LABELS[data.recommended]}, chosen from the analyst's theme.
            </p>
          </>
        ) : <p className="muted" style={{ margin: 0 }}>The analyst speaks up at the first key moment.</p>}
      </aside>
    </div></main></>
  );
}
