/**
 * Tests for spoken commentary planning: language filtering, voice choice, and the short speech queue.
 * They guarantee viewers only hear their own language and that speech keeps up by dropping play-by-play first.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { DELIVERY, MAX_PENDING_SPEECH, enqueueSpeech, interrupts, isSpeakable, pickVoice, serverSpeechRef, unseenLines }
  from "./speech";
import type { Intensity, TickerItem } from "../state/matchState";

function line(id: string, tone: TickerItem["tone"], language = "en", intensity: Intensity = "normal"): TickerItem {
  return { id, minute: "10'", text: id, tone, language, intensity };
}

const voice = (name: string, lang: string, localService = false, isDefault = false) =>
  ({ name, lang, localService, default: isDefault });

describe("isSpeakable", () => {
  it("speaks commentary, goals, and play-by-play in the viewer's language only", () => {
    expect(isSpeakable(line("a", "commentary", "es"), "es")).toBe(true);
    expect(isSpeakable(line("b", "play", "en"), "en-GB")).toBe(true);
    expect(isSpeakable(line("c", "play", "en"), "es")).toBe(false);
    expect(isSpeakable(line("d", "info", "en"), "en")).toBe(false);
  });
});

describe("pickVoice", () => {
  it("prefers a matching default voice, then an on-device one, and returns null without a match", () => {
    const voices = [voice("Remote ES", "es-ES"), voice("Local ES", "es-MX", true), voice("Default EN", "en-US", true, true)];
    expect(pickVoice(voices, "es")?.name).toBe("Local ES");
    expect(pickVoice(voices, "en")?.name).toBe("Default EN");
    expect(pickVoice(voices, "ja")).toBeNull();
  });
});

describe("enqueueSpeech", () => {
  it("keeps the queue short by dropping the calmest lines first, play-by-play before commentary", () => {
    const queue = enqueueSpeech([line("p1", "play")], [line("c1", "commentary"), line("g1", "goal", "en", "peak")]);
    expect(queue.map((i) => i.id)).toEqual(["c1", "g1"]);
    expect(queue).toHaveLength(MAX_PENDING_SPEECH);
    const raised = enqueueSpeech([line("c2", "commentary")], [line("x1", "play", "en", "raised"), line("p2", "play")]);
    expect(raised.map((i) => i.id)).toEqual(["c2", "x1"]);
  });

  it("drops the oldest line when nothing is droppable", () => {
    const queue = enqueueSpeech([line("c1", "commentary"), line("c2", "commentary")], [line("g1", "goal")]);
    expect(queue.map((i) => i.id)).toEqual(["c2", "g1"]);
  });
});

describe("unseenLines", () => {
  it("returns only new lines, oldest first, from a newest-first feed", () => {
    const feed = [line("n3", "play"), line("n2", "play"), line("n1", "play")];
    expect(unseenLines(feed, new Set(["n1"])).map((i) => i.id)).toEqual(["n2", "n3"]);
  });
});

describe("serverSpeechRef", () => {
  it("voices commentary in its receiving segment and play-by-play (goals included) by id, not event lines", () => {
    expect(serverSpeechRef({ ...line("moment-m3", "commentary", "es"), segment: "casual-es-none-none" }))
      .toEqual({ ref: "moment-m3", segment: "casual-es-none-none" });
    expect(serverSpeechRef(line("e9-pbp", "play"))).toEqual({ ref: "e9-pbp" });
    expect(serverSpeechRef(line("e10-pbp", "goal", "en", "peak"))).toEqual({ ref: "e10-pbp" });
    expect(serverSpeechRef(line("e11", "info"))).toBeNull();
  });
});

describe("excitement", () => {
  it("lifts pace and pitch with intensity and lets only goals interrupt", () => {
    expect(DELIVERY.peak.rate).toBeGreaterThan(DELIVERY.raised.rate);
    expect(DELIVERY.raised.pitch).toBeGreaterThan(DELIVERY.normal.pitch);
    expect(interrupts([line("p", "play"), line("g", "goal", "en", "peak")])).toBe(true);
    expect(interrupts([line("x", "play", "en", "raised")])).toBe(false);
  });
});
