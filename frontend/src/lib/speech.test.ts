/**
 * Tests for spoken commentary planning: language filtering, voice choice, and the short speech queue.
 * They guarantee viewers only hear their own language and that speech keeps up by dropping play-by-play first.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { MAX_PENDING_SPEECH, enqueueSpeech, isSpeakable, pickVoice, unseenLines } from "./speech";
import type { TickerItem } from "../state/matchState";

function line(id: string, tone: TickerItem["tone"], language = "en"): TickerItem {
  return { id, minute: "10'", text: id, tone, language };
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
  it("keeps the queue short by dropping the oldest play-by-play before commentary or goals", () => {
    const queue = enqueueSpeech([line("p1", "play")], [line("c1", "commentary"), line("g1", "goal")]);
    expect(queue.map((i) => i.id)).toEqual(["c1", "g1"]);
    expect(queue).toHaveLength(MAX_PENDING_SPEECH);
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
