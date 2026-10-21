/**
 * Pure planning for spoken commentary: which feed lines to speak, which voice to use, and how to keep up.
 * Only lines in the viewer's language are spoken, and the queue stays short so speech never lags far behind play.
 * Calmer lines are dropped first when lines arrive faster than they can be spoken, lines that waited too long are
 * skipped, goals interrupt anything, and close calls interrupt calm lines. Pace follows the replay speed (natural at
 * real time) and both pace and pitch lift audibly for close calls and goals. The viewer's own system voice is
 * preferred, then a natural-sounding male commentator voice; novelty voices are never chosen.
 */
import type { Intensity, TickerItem } from "../state/matchState";

/** At most this many lines wait to be spoken; older play-by-play goes first when the queue is full. */
export const MAX_PENDING_SPEECH = 2;
/** Same pace curve as the server's pace_for_speed: 1.0 at real time, +0.1 per tenfold speed-up, capped at 1.25. */
const REAL_TIME_PACE = 1.0;
const PACE_PER_DECADE = 0.1;
const MAX_PACE = 1.25;
const INTENSITY_PACE: Record<Intensity, number> = { normal: 1.0, raised: 1.08, peak: 1.15 };
const INTENSITY_PITCH: Record<Intensity, number> = { normal: 1.0, raised: 1.12, peak: 1.22 };
const NATURAL_VOICE = /natural|neural|enhanced|premium/i;
/** Commentator-style male voices across platforms; the broadcast persona is a male play-by-play voice. */
const MALE_VOICE =
  /\bmale\b|\b(daniel|arthur|oliver|george|ryan|thomas|aaron|alex|tom|rishi|guy|jorge|diego|luca|martin)\b/i;
const FEMALE_VOICE = /female|samantha|karen|moira|tessa|serena|kate|susan|zira|aria|jenny|sonia|libby|victoria/i;
const VOICE_SCORE = { natural: 8, systemDefault: 4, male: 3, locale: 1.5, local: 1, female: -3, robotic: -20 };
/** macOS novelty and legacy voices that sound robotic or comic; never chosen while anything else is available. */
const ROBOTIC_VOICE = new RegExp("^(albert|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|"
  + "trinoids|whisper|wobble|zarvox|junior|ralph|fred|kathy|eddy|flo|reed|rocko|sandy|shelley|grandma|grandpa)\\b", "i");
/** Broadcast-flavoured locale preferred within a language when several voices match. */
const PREFERRED_LOCALE: Record<string, string> = { en: "en-gb", es: "es-es", pt: "pt-br", fr: "fr-fr", de: "de-de" };
const INTENSITY_RANK: Record<Intensity, number> = { normal: 0, raised: 1, peak: 2 };

const SPOKEN_TONES: ReadonlySet<TickerItem["tone"]> = new Set(["commentary", "goal", "play"]);
/** Lines the server holds and can voice with neural speech: moment commentary and play-by-play, goals included. */
const SERVER_TONES: ReadonlySet<TickerItem["tone"]> = new Set(["commentary", "goal", "play"]);

/** The voice fields the planner needs, matching the browser's SpeechSynthesisVoice. */
export interface VoiceOption { name: string; lang: string; localService: boolean; default: boolean }

function baseLanguage(tag: string): string {
  return tag.toLowerCase().split(/[-_]/)[0];
}

/** Whether a feed line should be read aloud for a viewer using this language. */
export function isSpeakable(item: TickerItem, language: string): boolean {
  return SPOKEN_TONES.has(item.tone) && baseLanguage(item.language) === baseLanguage(language);
}

/** Typical speaking speed used to bound how long a line may take before the watchdog frees the queue. */
const CHARS_PER_SECOND = 14;
const WATCHDOG_GRACE_MS = 4000;
const MS_PER_SECOND = 1000;

/** Longest a line should take to speak at a rate; past this the line is treated as finished (browser stalls). */
export function watchdogMs(text: string, rate: number): number {
  return Math.round((text.length / CHARS_PER_SECOND / rate) * MS_PER_SECOND) + WATCHDOG_GRACE_MS;
}

/** Base speaking pace for a replay speed (match seconds per real second). */
export function paceForSpeed(speed: number): number {
  const pace = REAL_TIME_PACE + PACE_PER_DECADE * Math.log10(Math.max(speed, 1));
  return Math.min(Math.max(pace, REAL_TIME_PACE), MAX_PACE);
}

/** Rate and pitch for a line: the replay pace, lifted modestly for close calls and goals. */
export function deliveryFor(intensity: Intensity, speed: number): { rate: number; pitch: number } {
  return { rate: paceForSpeed(speed) * INTENSITY_PACE[intensity], pitch: INTENSITY_PITCH[intensity] };
}

/**
 * The commentator voice for a language: enhanced or neural voices first, then the viewer's system default, then
 * male voices, the broadcast locale, and on-device voices (which follow pitch and rate reliably, unlike online
 * voices); female-named voices rank lower and novelty voices are never chosen while anything else exists.
 */
export function pickVoice<V extends VoiceOption>(voices: readonly V[], language: string): V | null {
  const base = baseLanguage(language);
  const matching = voices.filter((v) => baseLanguage(v.lang) === base);
  const preferred = PREFERRED_LOCALE[base];
  const score = (v: V) => (NATURAL_VOICE.test(v.name) ? VOICE_SCORE.natural : 0)
    + (v.default ? VOICE_SCORE.systemDefault : 0) + (MALE_VOICE.test(v.name) ? VOICE_SCORE.male : 0)
    + (v.lang.toLowerCase().replace("_", "-") === preferred ? VOICE_SCORE.locale : 0)
    + (v.localService ? VOICE_SCORE.local : 0) + (FEMALE_VOICE.test(v.name) ? VOICE_SCORE.female : 0)
    + (ROBOTIC_VOICE.test(v.name) ? VOICE_SCORE.robotic : 0);
  return [...matching].sort((a, b) => score(b) - score(a))[0] ?? null;
}

/**
 * Whether a new batch should cut off what is being said: a goal always does, like a commentator jumping in, and a
 * close call does when the current line (null when silent) is a calm one.
 */
export function interrupts(incoming: readonly TickerItem[], current: Intensity | null = null): boolean {
  const top = Math.max(...incoming.map((item) => INTENSITY_RANK[item.intensity]), -1);
  return top === INTENSITY_RANK.peak || (top === INTENSITY_RANK.raised && current === "normal");
}

/** How long a queued line may wait before it is out of date: calm lines go stale fast, goals never do. */
export const STALE_AFTER_MS: Record<Intensity, number> = { normal: 4000, raised: 8000, peak: Infinity };

/** Whether a line that has waited waitedMs is too late to be worth saying. */
export function isStale(intensity: Intensity, waitedMs: number): boolean {
  return waitedMs > STALE_AFTER_MS[intensity];
}

/**
 * Add newly arrived lines (oldest first) to the queue, trimming it to MAX_PENDING_SPEECH by dropping the oldest of
 * the calmest lines first, and play-by-play before agent commentary at the same intensity.
 */
export function enqueueSpeech(pending: readonly TickerItem[], incoming: readonly TickerItem[]): TickerItem[] {
  const queue = [...pending, ...incoming];
  const weight = (item: TickerItem) => INTENSITY_RANK[item.intensity] * 2 + (item.tone === "play" ? 0 : 1);
  while (queue.length > MAX_PENDING_SPEECH) {
    const lowest = Math.min(...queue.map(weight));
    queue.splice(queue.findIndex((item) => weight(item) === lowest), 1);
  }
  return queue;
}

/** Where the server can voice a line: its feed reference and, for moment commentary, the receiving segment. */
export function serverSpeechRef(item: TickerItem): { ref: string; segment?: string } | null {
  if (!SERVER_TONES.has(item.tone)) return null;
  return item.tone === "commentary" ? { ref: item.id, segment: item.segment } : { ref: item.id };
}

/** The newest line worth speaking right away when voice is switched on, so the viewer hears something at once. */
export function latestSpeakable(feed: readonly TickerItem[], language: string): TickerItem | null {
  return feed.find((item) => isSpeakable(item, language)) ?? null;
}

/** Lines in the feed (newest first) that have not been seen yet, returned oldest first. */
export function unseenLines(feed: readonly TickerItem[], seen: ReadonlySet<string>): TickerItem[] {
  return feed.filter((item) => !seen.has(item.id)).reverse();
}
