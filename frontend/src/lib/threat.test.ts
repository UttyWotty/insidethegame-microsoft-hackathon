/**
 * Tests for the expected threat (xT) graphics logic.
 * They check the line-breaker flash, card rows per persona, danger leaderboard rows, and the analyst stat rows.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { LEADERBOARD_SIZE } from "./broadcastStats";
import { analystStatRows, dangerRows, THREAT_CARD_MS, threatCardRows, threatFlash, type ThreatFlash } from "./threat";
import type { EventUpdate, KeyMoment, MatchMetadata, Snapshot, ThreatLeader } from "../types";

const match = {
  match_id: "m", competition: "c", venue: "v", kickoff_utc: "", seed: 1,
  home: { team_id: "kba", name: "Home", short_name: "HOM", style: { label: "x" }, players: [] },
  away: { team_id: "irv", name: "Away", short_name: "AWY", style: { label: "y" }, players: [] },
} as MatchMetadata;

const threatMoment: KeyMoment = {
  moment_id: "m-9", kind: "threat_created", period: 1, match_second: 900, minute: 16, importance: 0.5, team_id: "irv",
  player_ids: ["irv-08", "irv-09"],
  facts: { passer: "Caio Wexley", receiver: "Cyrus Rocha", xt_added: 0.031, xt_start: 0.012, xt_end: 0.043,
           opponents_bypassed: 4, lines_broken: "midfield and defence", length_m: 22.4 },
};

const update = (moments: KeyMoment[]): EventUpdate => ({
  event: {
    event_id: "e1", sequence: 1, period: 1, match_second: 900, minute: 16, event_type: "pass", team_id: "irv",
    player_id: "irv-08", start: { x: 50, y: 30 }, end: { x: 80, y: 30 }, outcome: "success", receiver_id: "irv-09",
    under_pressure: false, length_m: 22.4, ball_speed_kmh: null, shot_result: null, score: { home: 0, away: 0 },
  },
  xg: null, pass_quality: null, moments,
  rhythm: { momentum: 0, home_threat: 0, away_threat: 0, chaos: 0, turnovers_per_minute: 0, home_pass_share: 0.5, state: "balanced" },
});

const flash = threatFlash(update([threatMoment]), "kba", 1000) as ThreatFlash;

const leader = (id: string, team: string, xt: number): ThreatLeader => ({
  player_id: id, name: `Player ${id}`, team_id: team, xt_added: xt, line_breaking_passes: 1, opponents_bypassed: 3,
});

describe("threatFlash", () => {
  it("is null for updates without a threat_created moment", () => {
    expect(threatFlash(update([]), "kba", 1)).toBeNull();
    expect(threatFlash(update([{ ...threatMoment, kind: "difficult_pass" }]), "kba", 1)).toBeNull();
  });

  it("carries the facts, the side, and the arrival time", () => {
    expect(flash).toEqual({ momentId: "m-9", passer: "Caio Wexley", receiver: "Cyrus Rocha", side: "away",
                            xtAdded: 0.031, xtStart: 0.012, xtEnd: 0.043, bypassed: 4, lines: "midfield and defence",
                            at: 1000 });
    expect(THREAT_CARD_MS).toBe(6000);
  });
});

describe("threatCardRows", () => {
  it("gives the analyst four rows including xT", () => {
    expect(threatCardRows(flash, "analyst")).toEqual([
      ["xT added", "+0.031"], ["xT", "0.012 to 0.043"], ["Opponents bypassed", "4"], ["Lines broken", "Midfield, defence"],
    ]);
  });

  it("gives every other persona only the bypassed and lines rows", () => {
    expect(threatCardRows(flash, "casual")).toEqual([["Opponents bypassed", "4"], ["Lines broken", "Midfield, defence"]]);
    expect(threatCardRows({ ...flash, lines: "defence", bypassed: null }, "newcomer"))
      .toEqual([["Opponents bypassed", "-"], ["Lines broken", "Defence"]]);
  });
});

describe("dangerRows", () => {
  it("sorts by xT added, limits to the leaderboard size, and maps sides", () => {
    const leaders = [leader("a", "kba", 0.1), leader("b", "irv", 0.4), ...[1, 2, 3, 4, 5].map((i) => leader(`c${i}`, "kba", 0.01 * i))];
    const rows = dangerRows(leaders, match);
    expect(rows).toHaveLength(LEADERBOARD_SIZE);
    expect(rows[0]).toEqual({ playerId: "b", name: "Player b", side: "away", value: 0.4 });
    expect(rows[1].side).toBe("home");
    expect(rows.map((r) => r.value)).toEqual([...rows.map((r) => r.value)].sort((x, y) => y - x));
  });

  it("returns no rows when the snapshot has no leaders", () => {
    expect(dangerRows(undefined, match)).toEqual([]);
  });
});

describe("analystStatRows", () => {
  it("formats xT to two decimals and counts line-breaking passes", () => {
    const snapshot = {
      home: { stats: { xt_added: 1.2345, line_breaking_passes: 31 } }, away: { stats: { xt_added: 0.9, line_breaking_passes: 27 } },
    } as unknown as Snapshot;
    const rows = analystStatRows(snapshot);
    expect(rows.map((r) => r.label)).toEqual(["Expected threat (xT)", "Line-breaking passes"]);
    expect(rows[0].format(rows[0].home)).toBe("1.23");
    expect(rows[0].format(rows[0].away)).toBe("0.90");
    expect(rows[1].format(rows[1].home)).toBe("31");
  });
});
