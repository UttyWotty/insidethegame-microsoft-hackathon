/**
 * TypeScript mirror of the backend's machine-readable contract: events, snapshots, cues, and recaps.
 * Every server-sent message is parsed into one of these shapes before reaching the UI.
 * Keep this file aligned with the Python domain, analytics, and orchestration models.
 */

export type PersonaKey = "analyst" | "casual" | "superfan" | "player_tracker" | "newcomer";
export type Layout = "stat_panel" | "lower_third" | "hype_banner" | "player_tag" | "explainer_card";
export type RhythmState = "balanced" | "home_control" | "away_control" | "home_pressure" | "away_pressure" | "chaos";
export type OutputSource = "model" | "model_retry" | "fallback";

export interface Point { x: number; y: number }

export interface Player { player_id: string; name: string; shirt_number: number; position: "GK" | "DF" | "MF" | "FW" }

export interface Team { team_id: string; name: string; short_name: string; style: { label: string }; players: Player[] }

export interface MatchMetadata {
  match_id: string; competition: string; venue: string; kickoff_utc: string; seed: number; home: Team; away: Team;
}

export interface SessionInfo { session_id: string; status: "pending" | "live" | "finished"; speed: number; match: MatchMetadata }

export interface MatchEvent {
  event_id: string; sequence: number; period: number; match_second: number; minute: number; event_type: string;
  team_id: string | null; player_id: string | null; start: Point | null; end: Point | null; outcome: string | null;
  receiver_id: string | null; under_pressure: boolean; length_m: number | null; ball_speed_kmh: number | null;
  shot_result: string | null; score: { home: number; away: number };
}

export interface Rhythm {
  momentum: number; home_threat: number; away_threat: number; chaos: number; turnovers_per_minute: number;
  home_pass_share: number; state: RhythmState;
}

export interface KeyMoment {
  moment_id: string; kind: string; period: number; match_second: number; minute: number; importance: number;
  team_id: string | null; player_ids: string[]; facts: Record<string, string | number | boolean | null>;
}

export type TrackingFrame = [string, number, number][];

/** The fastest player on or toward the ball in a tracking frame, at sprint speed (25.2 km/h or more). */
export interface SprintTag { player_id: string; speed_kmh: number }

/** Broadcast facts for a shot: placement and keeper in metres from the goal centre (positive to the shooter's right). */
export interface ShotCardInfo {
  result: string; xg: number; speed_kmh: number | null; distance_m: number; angle_deg: number;
  placement_y: number | null; placement_z: number | null; keeper_y: number | null;
}

/** Expected threat (xT) one completed pass or carry added, and any line break, mirroring ThreatAction.to_dict(). */
export interface ThreatInfo {
  event_id: string; team_id: string; player_id: string; action: "pass" | "carry"; xt_start: number; xt_end: number;
  xt_added: number; opponents_bypassed: number | null; lines_broken: string[]; breaks_line: boolean;
}

/** One row of the danger leaderboard: the players whose passes and carries added the most xT. */
export interface ThreatLeader {
  player_id: string; name: string; team_id: string; xt_added: number; line_breaking_passes: number;
  opponents_bypassed: number;
}

export interface EventUpdate {
  event: MatchEvent; xg: number | null; pass_quality: { difficulty: number } | null; rhythm: Rhythm; moments: KeyMoment[];
  positions?: TrackingFrame | null;
  sprint?: SprintTag | null;
  shot?: ShotCardInfo | null;
  /** Live home win, draw, and away win probabilities after this event. */
  win?: WinProbability | null;
  /** xT added by a completed pass or carry, or null for any other event. */
  threat?: ThreatInfo | null;
}

export interface WinProbability { home: number; draw: number; away: number }
/** Distance covered (km) and top speed (km/h) per player. */
export type PhysicalStats = Record<string, { distance_km: number; top_kmh: number }>;

export type StatBlock = Record<string, number>;

export interface TeamSnapshot { team_id: string; name: string; short_name: string; possession_pct: number; stats: StatBlock }

export interface PlayerSnapshot extends StatBlock { }

export interface Snapshot {
  match_id: string; period: number | null; minute: number | null; match_second: number | null;
  score: { home: number; away: number }; home: TeamSnapshot; away: TeamSnapshot; rhythm: Rhythm | null;
  players: Record<string, PlayerSnapshot & { name?: string; team_id?: string }>;
  /** Distance and top speed per player from tracking, when the live session sends them. */
  physical?: PhysicalStats;
  /** Danger leaderboard by expected threat (xT) added, at most five players. */
  threat_leaders?: ThreatLeader[];
  /** Each team's out-of-possession shape over the last five minutes, null until it has enough samples. */
  shape?: { home: TeamShape | null; away: TeamShape | null };
}

/** How high a team defends, from its back-line height. */
export type Block = "high" | "mid" | "low";

/** A team's smoothed out-of-possession shape in metres, mirroring TeamShapeReading.to_dict(). */
export interface TeamShape {
  team_id: string; line_height_m: number; length_m: number; width_m: number; compactness_m: number; block: Block;
  samples: number; window_minutes: number;
}

/** Both teams' smoothed back-line heights at one minute; null before a team has a reading. */
export interface ShapeTimelinePoint {
  period: number; match_second: number; minute: number; home_line_m: number | null; away_line_m: number | null;
}

/** A shape_shift moment as the studio timeline marks it. */
export interface ShapeShiftMark {
  moment_id: string; minute_label: string; period: number; match_second: number; team_id: string;
  direction: "dropped" | "pushed_up"; line_before_m: number; line_after_m: number;
}

/** The whole match's line-height timeline and shape shifts, whatever the studio window. */
export interface ShapeStudio { timeline: ShapeTimelinePoint[]; shifts: ShapeShiftMark[] }

/** One output's provenance; problems is present only when the outcome recorded any (e.g. "template failed"). */
export interface Provenance { source: OutputSource; attempts: number; latency_ms: number; problems?: string[] }

export interface FactCheck { verdict: "approved" | "revised" | "replaced" | "skipped"; checker: string; issues: string[] }

export interface OverlayCue {
  cue_id: string; moment_id: string; viewer_id: string; persona: PersonaKey; language: string; layout: Layout;
  period: number; display_from_s: number; duration_s: number; priority: number; title: string; body: string;
  stat_callouts: { label: string; value: string }[]; commentary: string; commentary_language: string;
  commentary_intensity: "normal" | "raised" | "peak"; theme: string;
  provenance: Record<string, Provenance> & { fact_check?: FactCheck; commentary_check?: FactCheck };
  replay?: boolean;
}

export interface Recap {
  stage: "half_time" | "full_time"; source: OutputSource; latency_ms: number;
  persona?: PersonaKey; take?: { headline: string; take: string }; take_source?: OutputSource;
  recap: { headline: string; summary: string; turning_points: string[]; standout_player: string; tactical_story: string };
}

/** One stored tracking frame of a highlights clip, positions in the absolute home frame. */
export interface HighlightFrame {
  period: number; match_second: number; event_type: string; player_id: string | null; ball: [number, number];
  positions: TrackingFrame;
}

/** Fields every replayed key moment of the automated highlights reel carries. */
export interface HighlightClipBase {
  moment_id: string; kind: string; minute: string; period: number; match_second: number; title: string;
  /** Main player named in the moment's facts (scorer, shooter, passer), or null. */
  actor: string | null; commentary: string; language: string; intensity: "normal" | "raised" | "peak";
}

/**
 * One replayed key moment of the automated highlights reel. A shot clip ("story") carries the shot's instant-replay
 * keyframes (build-up and the ball's flight); any other clip ("frames") carries the stored frames around the moment.
 */
export type HighlightClip =
  | (HighlightClipBase & { playback: "frames"; frames: HighlightFrame[] })
  | (HighlightClipBase & { playback: "story"; frames: ReplayKeyframe[] });

/** One instant-replay keyframe in the absolute home frame: a build-up action, the strike, or the ball's arrival. */
export interface ReplayKeyframe extends HighlightFrame {
  phase: "build_up" | "shot" | "flight"; receiver_id: string | null;
}

/** The last completed pass to the shooter; threat fields are null or empty when no threat was stored. */
export interface ReplayAssist {
  passer_id: string; length_m: number; difficulty: number | null; xt_added: number | null;
  opponents_bypassed: number | null; lines_broken: string[]; breaks_line: boolean;
}

/** The shooting team's possession: completed passes, seconds, xT built, and the drawn ball path (absolute frame). */
export interface ReplayBuildUp { passes: number; duration_s: number; xt_added: number; path: [number, number][] }

/** Shot analysis of an instant replay, mirroring ShotAnalysis.to_dict(); cone points are in the absolute frame. */
export interface ReplayAnalysis {
  shot_event_id: string; shooter_id: string; team_id: string; card: ShotCardInfo; xg: number; goal_chance_pct: number;
  under_pressure: boolean; cone: [number, number][]; defenders_in_cone: number; keeper_in_cone: boolean;
  build_up: ReplayBuildUp; assist: ReplayAssist | null;
}

/** The instant replay story of one shot: keyframes plus analysis. */
export interface ReplayStory { period: number; at: number; frames: ReplayKeyframe[]; analysis: ReplayAnalysis }

export interface HighlightReel { stage: "half_time" | "full_time"; headline: string; clips: HighlightClip[] }

export type StudioVisual = "heat_map" | "pressing" | "pass_network" | "space_control";
export interface SpaceControl {
  owners: number[][]; home_share: number; home_thirds: number[];
  /** Players in the frame the control was computed from, absolute home frame. */
  positions?: TrackingFrame;
}
export interface PassNetwork {
  nodes: { player_id: string; x: number; y: number; passes: number }[]; links: [string, string, number][];
}
export interface StudioTeam { team_id: string; heat: number[][]; pressing: number[][]; network: PassNetwork }
/** The Match Analyst's latest explanation, which picks the recommended studio visual. */
export interface StudioAnalyst {
  minute: string; kind: string; headline: string; why_it_matters: string; theme: string; source: "agent" | "template";
}
export interface StudioPayload {
  window: "match" | "last_15"; events: number; teams: { home: StudioTeam; away: StudioTeam };
  control: SpaceControl | null; analyst: StudioAnalyst | null; recommended: StudioVisual;
  shape: ShapeStudio;
}

export interface PersonaInfo {
  key: PersonaKey; name: string; audience: string; voice: string; max_words: number; overlay_style: Layout;
}

export interface ClubInfo { key: string; name: string; short_name: string; venue: string; style: string; team_id: string }

export interface ViewerSettings { persona: PersonaKey; language: string; team: string | null; player: string | null }

export interface CompanionReply {
  question: string; answer: string; stat_callouts: { label: string; value: string }[]; follow_ups: string[];
  language: string; source: OutputSource; latency_ms: number;
}

export interface TimelineEntry { moment_id: string; minute: string; kind: string; importance: number; status: string }

export interface BroadcastRecord {
  moment_id: string; minute: string; kind: string; importance: number; degraded: boolean;
  status: "aired" | "held" | "released"; commentary: string;
  explanation: { headline: string; why_it_matters: string; evidence: string[]; theme: string };
  cues: OverlayCue[];
}

export interface PipelineHealth {
  moments: number; cues: number; mean_card_latency_ms: number; skipped: number;
  source_rates: Record<string, Record<string, number>>; fact_checks: Record<string, number>;
}

export interface TraceStep {
  executor_id: string; agent: string; status: "running" | "done" | "failed"; started_ms: number;
  ended_ms: number | null; note: string;
}
/** Live trace of one moment's multi-agent workflow. */
export interface AgentTraceInfo {
  moment_id: string; minute: string; kind: string; finished: boolean; elapsed_ms: number; steps: TraceStep[];
  handoffs: [string, string][];
}

export interface ProducerSummary {
  hold: boolean; segments: number; timeline: TimelineEntry[]; records: BroadcastRecord[]; health: PipelineHealth;
  traces: AgentTraceInfo[];
}
