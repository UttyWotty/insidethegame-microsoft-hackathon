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

export interface EventUpdate {
  event: MatchEvent; xg: number | null; pass_quality: { difficulty: number } | null; rhythm: Rhythm; moments: KeyMoment[];
  positions?: TrackingFrame | null;
}

export type StatBlock = Record<string, number>;

export interface TeamSnapshot { team_id: string; name: string; short_name: string; possession_pct: number; stats: StatBlock }

export interface PlayerSnapshot extends StatBlock { }

export interface Snapshot {
  match_id: string; period: number | null; minute: number | null; match_second: number | null;
  score: { home: number; away: number }; home: TeamSnapshot; away: TeamSnapshot; rhythm: Rhythm | null;
  players: Record<string, PlayerSnapshot & { name?: string; team_id?: string }>;
}

export interface Provenance { source: OutputSource; attempts: number; latency_ms: number }

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

export interface ProducerSummary {
  hold: boolean; segments: number; timeline: TimelineEntry[]; records: BroadcastRecord[]; health: PipelineHealth;
}
