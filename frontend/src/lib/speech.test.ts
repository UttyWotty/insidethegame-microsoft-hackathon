/**
 * Tests for spoken commentary planning: language filtering, voice choice, and the short speech queue.
 * They guarantee viewers only hear their own language and that speech keeps up by dropping play-by-play first.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  MAX_PENDING_SPEECH, deliveryFor, enqueueSpeech, interrupts, isSpeakable, isStale, latestSpeakable, paceForSpeed,
  pickVoice, serverSpeechRef, unseenLines, watchdogMs,
} from "./speech";
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

describe("commentator voice", () => {
  it("prefers enhanced voices, then the system default, then male voices over online and female ones", () => {
    const voices = [voice("Samantha", "en-US", true), voice("Google UK English Female", "en-GB"),
                    voice("Google UK English Male", "en-GB"), voice("Daniel", "en-GB", true, true)];
    expect(pickVoice(voices, "en")?.name).toBe("Daniel");
    expect(pickVoice(voices.slice(0, 3), "en")?.name).toBe("Google UK English Male");
    expect(pickVoice([...voices, voice("Daniel (Enhanced)", "en-GB", true)], "en")?.name).toBe("Daniel (Enhanced)");
  });

  it("never picks novelty voices, even when one is the system default", () => {
    const voices = [voice("Bubbles", "en-US", true, true), voice("Zarvox", "en-US", true), voice("Daniel", "en-GB", true)];
    expect(pickVoice(voices, "en")?.name).toBe("Daniel");
  });
});

describe("pickVoice", () => {
  it("prefers the broadcast locale, then the default voice, and returns null without a match", () => {
    const voices = [voice("Remote ES", "es-ES"), voice("Local ES", "es-MX", true), voice("Default EN", "en-US", true, true)];
    expect(pickVoice(voices, "es")?.name).toBe("Remote ES");
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

describe("pace", () => {
  it("speaks naturally at real time and quicker for faster replays, within a cap", () => {
    expect(paceForSpeed(1)).toBe(1);
    expect(paceForSpeed(10)).toBeCloseTo(1.1);
    expect(paceForSpeed(600)).toBe(1.25);
    expect(deliveryFor("normal", 1)).toEqual({ rate: 1, pitch: 1 });
  });

  it("gives the watchdog longer for longer and slower lines", () => {
    expect(watchdogMs("x".repeat(140), 1)).toBeGreaterThan(watchdogMs("x".repeat(14), 1));
    expect(watchdogMs("x".repeat(140), 1)).toBeGreaterThan(watchdogMs("x".repeat(140), 1.25));
  });
});

describe("excitement", () => {
  it("lifts pace and pitch audibly with intensity", () => {
    expect(deliveryFor("peak", 10).rate).toBeGreaterThan(deliveryFor("raised", 10).rate);
    expect(deliveryFor("raised", 1).pitch).toBeGreaterThanOrEqual(1.1);
    expect(deliveryFor("peak", 1).pitch).toBeGreaterThan(deliveryFor("raised", 1).pitch);
  });

  it("lets goals interrupt anything and close calls interrupt only calm lines", () => {
    expect(interrupts([line("p", "play"), line("g", "goal", "en", "peak")], "raised")).toBe(true);
    expect(interrupts([line("x", "play", "en", "raised")], "normal")).toBe(true);
    expect(interrupts([line("x", "play", "en", "raised")], "raised")).toBe(false);
    expect(interrupts([line("x", "play", "en", "raised")])).toBe(false);
    expect(interrupts([line("p", "play")], "normal")).toBe(false);
  });

  it("skips calm lines that waited too long but always says the goal", () => {
    expect(isStale("normal", 5000)).toBe(true);
    expect(isStale("normal", 1000)).toBe(false);
    expect(isStale("raised", 5000)).toBe(false);
    expect(isStale("peak", 60000)).toBe(false);
  });
});

describe("latestSpeakable", () => {
  it("returns the newest line in the viewer's language so switching voice on speaks at once", () => {
    const feed = [line("i1", "info"), line("p2", "play"), line("p1", "play")];
    expect(latestSpeakable(feed, "en")?.id).toBe("p2");
    expect(latestSpeakable(feed, "es")).toBeNull();
  });
});
