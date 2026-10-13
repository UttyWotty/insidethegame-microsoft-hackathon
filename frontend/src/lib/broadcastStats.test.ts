/**
 * Tests for live broadcast stat helpers.
 * They check win bar percentages, event pop-up rules and expiry, and leaderboard ordering.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { eventPopup, LEADERBOARD_SIZE, leaderboard, POPUP_MS, winPercentages } from "./broadcastStats";
import type { MatchEvent, MatchMetadata } from "../types";

const event = (event_type: string, outcome: string | null = "success"): MatchEvent => ({
  event_id: "e", sequence: 1, period: 1, match_second: 10, minute: 1, event_type, team_id: "h", player_id: "p1",
  start: null, end: null, outcome, receiver_id: null, under_pressure: false, length_m: null, ball_speed_kmh: null,
  shot_result: null, score: { home: 0, away: 0 },
});

describe("broadcast stats", () => {
  it("rounds win probabilities to a bar that adds up to 100", () => {
    expect(winPercentages({ home: 0.456, draw: 0.271, away: 0.273 })).toEqual({ home: 46, draw: 27, away: 27 });
  });

  it("pops up tackles won, interceptions, and saves briefly", () => {
    expect(eventPopup(event("tackle"), 1000, 1500)).toEqual({ playerId: "p1", text: "TACKLE WON" });
    expect(eventPopup(event("tackle", "failure"), 1000, 1500)).toBeNull();
    expect(eventPopup(event("interception"), 1000, 1000 + POPUP_MS + 1)).toBeNull();
    expect(eventPopup(event("pass"), 1000, 1500)).toBeNull();
  });

  it("ranks the leaderboard and keeps it short", () => {
    const players = Array.from({ length: 8 }, (_, i) => ({ player_id: `h${i}`, name: `H ${i}` }));
    const match = { home: { players }, away: { players: [] } } as unknown as MatchMetadata;
    const physical = Object.fromEntries(players.map((p, i) => [p.player_id, { distance_km: i, top_kmh: 30 - i }]));
    const rows = leaderboard(physical, match, "distance_km");
    expect(rows).toHaveLength(LEADERBOARD_SIZE);
    expect(rows[0]).toMatchObject({ playerId: "h7", value: 7, side: "home" });
    expect(leaderboard(physical, match, "top_kmh")[0].playerId).toBe("h0");
  });
});
