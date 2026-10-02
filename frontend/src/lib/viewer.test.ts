/**
 * Tests for viewer resolution defaults and canonicalisation.
 * They guarantee every persona produces a valid, minimal segment request.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { resolveViewer } from "./viewer";
import type { MatchMetadata } from "../types";

const match = {
  match_id: "m", competition: "c", venue: "v", kickoff_utc: "", seed: 1,
  home: { team_id: "kba", name: "K", short_name: "KBA", style: { label: "" }, players: [
    { player_id: "kba-01", name: "Keeper", shirt_number: 1, position: "GK" },
    { player_id: "kba-09", name: "Nine", shirt_number: 9, position: "FW" }] },
  away: { team_id: "irv", name: "I", short_name: "IRV", style: { label: "" }, players: [] },
} as MatchMetadata;

describe("resolveViewer", () => {
  it("defaults the superfan to the home club and keeps a valid choice", () => {
    expect(resolveViewer({ persona: "superfan", language: "en", team: null, player: null }, match).team).toBe("kba");
    expect(resolveViewer({ persona: "superfan", language: "en", team: "irv", player: null }, match).team).toBe("irv");
  });
  it("defaults the player tracker to the home number 9", () => {
    expect(resolveViewer({ persona: "player_tracker", language: "en", team: null, player: "ghost" }, match).player).toBe("kba-09");
  });
  it("clears preferences a persona does not use", () => {
    expect(resolveViewer({ persona: "analyst", language: "es", team: "kba", player: "kba-09" }, match))
      .toEqual({ persona: "analyst", language: "es", team: null, player: null });
  });
});
