/**
 * Tests for the producer's outcome problem summary.
 * They check that clean moments yield nothing, shared outputs appear once, and per-viewer outputs name segments.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { audience, outcomeProblems, problemLabel, problemText } from "./outcomeProblems";
import type { OverlayCue, PersonaKey, Provenance } from "../types";

const DEGRADED = ["workflow degraded"];
const FAILED = ["workflow degraded", "template failed"];

function prov(problems?: string[]): Provenance {
  return { source: "fallback", attempts: 0, latency_ms: 0, ...(problems ? { problems } : {}) };
}

function cue(persona: PersonaKey, provenance: Record<string, Provenance>): OverlayCue {
  return {
    cue_id: `m-${persona}`, moment_id: "m", viewer_id: persona, persona, language: "en", layout: "stat_panel",
    period: 1, display_from_s: 0, duration_s: 6, priority: 0.5, title: "t", body: "b", stat_callouts: [],
    commentary: "c", commentary_language: "en", commentary_intensity: "normal", theme: "", provenance,
  };
}

const clean: Record<string, Provenance> = { explanation: prov(), commentary: prov(), card: prov() };

describe("outcomeProblems", () => {
  it("returns nothing when no output has problems", () => {
    expect(outcomeProblems([cue("analyst", clean), cue("casual", clean)])).toEqual([]);
    expect(outcomeProblems([])).toEqual([]);
  });

  it("lists shared outputs once and names only the audience whose card failed", () => {
    const degraded = { explanation: prov(DEGRADED), commentary: prov(DEGRADED), card: prov(DEGRADED) };
    const lines = outcomeProblems([
      cue("analyst", degraded), cue("player_tracker", { ...degraded, card: prov(FAILED) }), cue("newcomer", degraded),
    ]);
    expect(lines.map((l) => `${problemLabel(l)}: ${problemText(l)}`)).toEqual([
      "Explanation: workflow degraded",
      "Commentary: workflow degraded",
      "Card (analyst en, newcomer en): workflow degraded",
      "Card (player tracker en): workflow degraded; template failed",
    ]);
  });

  it("omits audiences when every viewer with that output shares the problems", () => {
    const failedCard = { ...clean, card: prov(FAILED) };
    const lines = outcomeProblems([cue("analyst", failedCard), cue("casual", failedCard)]);
    expect(lines).toHaveLength(1);
    expect(problemLabel(lines[0])).toBe("Card");
    expect(problemText(lines[0])).toBe("workflow degraded; template failed");
  });

  it("counts translations only among cues that have one and dedupes repeated notes", () => {
    const timedOut = ["timed out after 8s", "timed out after 8s"];
    const translated = { ...clean, translation: prov(timedOut) };
    const lines = outcomeProblems([cue("analyst", clean), cue("superfan", translated)]);
    expect(lines.map((l) => [problemLabel(l), problemText(l)])).toEqual([["Translation", "timed out after 8s"]]);
  });

  it("treats an empty problems list as no problems", () => {
    expect(outcomeProblems([cue("analyst", { ...clean, card: prov([]) })])).toEqual([]);
  });

  it("gives distinct labels to per-viewer groups whose audiences share a persona (QA)", () => {
    const degraded = { explanation: prov(DEGRADED), commentary: prov(DEGRADED), card: prov(DEGRADED) };
    const en = cue("analyst", degraded);
    const fr = { ...cue("analyst", { ...degraded, card: prov(FAILED) }), viewer_id: "analyst-fr", language: "fr" };
    const cards = outcomeProblems([en, fr]).filter((l) => l.key === "card");
    expect(cards).toHaveLength(2);
    expect(new Set(cards.map(problemLabel)).size).toBe(2);
  });

  it("names audiences by segment, including club or player when the segment id carries them", () => {
    const base = cue("superfan", clean);
    expect(audience({ ...base, viewer_id: "superfan-es-kba-none", language: "es" })).toBe("superfan es kba");
    expect(audience({ ...base, viewer_id: "analyst-fr-none-none", persona: "analyst", language: "fr" }))
      .toBe("analyst fr");
    expect(audience({ ...base, viewer_id: "superfan-en-GB-kba-none" })).toBe("superfan en-GB kba");
    expect(audience({ ...base, viewer_id: "player_tracker-ja-none-p9", persona: "player_tracker" }))
      .toBe("player tracker ja p9");
    expect(audience(base)).toBe("superfan en");
  });

  it("uses the segment language when an untranslated cue reports English", () => {
    const degraded = { explanation: prov(DEGRADED), commentary: prov(DEGRADED), card: prov(DEGRADED) };
    const en = { ...cue("analyst", degraded), viewer_id: "analyst-en-none-none" };
    const fr = { ...cue("analyst", { ...degraded, card: prov(FAILED) }), viewer_id: "analyst-fr-none-none" };
    expect(outcomeProblems([en, fr]).filter((l) => l.key === "card").map(problemLabel))
      .toEqual(["Card (analyst en)", "Card (analyst fr)"]);
  });

  it("gives every line a unique id that is stable for the same cues", () => {
    const degraded = { explanation: prov(DEGRADED), commentary: prov(DEGRADED), card: prov(DEGRADED) };
    const viewer = (persona: PersonaKey, language: string, card: string[]): OverlayCue => ({
      ...cue(persona, { ...degraded, card: prov(card), translation: prov(["timed out after 8s"]) }),
      viewer_id: `${persona}-${language}-none-none`, language,
    });
    const cues = [viewer("analyst", "en", DEGRADED), viewer("analyst", "fr", FAILED), viewer("casual", "fr", FAILED)];
    const ids = outcomeProblems(cues).map((l) => l.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(outcomeProblems(cues).map((l) => l.id)).toEqual(ids);
    expect(outcomeProblems(cues).map(problemLabel)).toEqual([
      "Explanation", "Commentary", "Card (analyst en)", "Card (analyst fr, casual fr)", "Translation",
    ]);
  });
  it("labels club and dashed player segments distinctly within one persona and language (QA round 2)", () => {
    const degraded = { explanation: prov(DEGRADED), commentary: prov(DEGRADED), card: prov(DEGRADED) };
    const seg = (persona: PersonaKey, viewerId: string, card: string[]): OverlayCue =>
      ({ ...cue(persona, { ...degraded, card: prov(card) }), viewer_id: viewerId, language: "en" });
    const lines = outcomeProblems([
      seg("superfan", "superfan-fr-kba-none", FAILED), seg("superfan", "superfan-fr-irv-none", DEGRADED),
      seg("player_tracker", "player_tracker-fr-none-kba-07", FAILED),
      seg("player_tracker", "player_tracker-fr-none-irv-09", DEGRADED),
    ]);
    expect(lines.filter((l) => l.key === "card").map(problemLabel)).toEqual([
      "Card (superfan fr kba, player tracker fr kba 07)", "Card (superfan fr irv, player tracker fr irv 09)",
    ]);
    const ids = lines.map((l) => l.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
