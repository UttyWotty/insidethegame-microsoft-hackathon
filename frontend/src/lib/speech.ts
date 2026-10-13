/**
 * Pure planning for spoken commentary: which feed lines to speak, which voice to use, and how to keep up.
 * Only lines in the viewer's language are spoken, and the queue stays short so speech never lags far behind play.
 * Play-by-play is dropped before agent commentary and goals when lines arrive faster than they can be spoken.
 */
import type { TickerItem } from "../state/matchState";

/** At most this many lines wait to be spoken; older play-by-play goes first when the queue is full. */
export const MAX_PENDING_SPEECH = 2;
/** Slightly brisk delivery, closer to live commentary than the default reading pace. */
export const SPEECH_RATE = 1.08;

const SPOKEN_TONES: ReadonlySet<TickerItem["tone"]> = new Set(["commentary", "goal", "play"]);
/** Lines the server holds and can voice with neural speech; event lines such as goals are spoken on-device. */
const SERVER_TONES: ReadonlySet<TickerItem["tone"]> = new Set(["commentary", "play"]);
const DROPPABLE_TONE: TickerItem["tone"] = "play";

/** The voice fields the planner needs, matching the browser's SpeechSynthesisVoice. */
export interface VoiceOption { name: string; lang: string; localService: boolean; default: boolean }

function baseLanguage(tag: string): string {
  return tag.toLowerCase().split(/[-_]/)[0];
}

/** Whether a feed line should be read aloud for a viewer using this language. */
export function isSpeakable(item: TickerItem, language: string): boolean {
  return SPOKEN_TONES.has(item.tone) && baseLanguage(item.language) === baseLanguage(language);
}

/** The best voice for a language: matching voices first, preferring the system default, then on-device voices. */
export function pickVoice<V extends VoiceOption>(voices: readonly V[], language: string): V | null {
  const matching = voices.filter((v) => baseLanguage(v.lang) === baseLanguage(language));
  const score = (v: V) => (v.default ? 2 : 0) + (v.localService ? 1 : 0);
  return [...matching].sort((a, b) => score(b) - score(a))[0] ?? null;
}

/** Add newly arrived lines (oldest first) to the queue, trimming it to MAX_PENDING_SPEECH. */
export function enqueueSpeech(pending: readonly TickerItem[], incoming: readonly TickerItem[]): TickerItem[] {
  const queue = [...pending, ...incoming];
  while (queue.length > MAX_PENDING_SPEECH) {
    const droppable = queue.findIndex((item) => item.tone === DROPPABLE_TONE);
    queue.splice(droppable >= 0 ? droppable : 0, 1);
  }
  return queue;
}

/** Where the server can voice a line: its feed reference and, for moment commentary, the receiving segment. */
export function serverSpeechRef(item: TickerItem): { ref: string; segment?: string } | null {
  if (!SERVER_TONES.has(item.tone)) return null;
  return item.tone === "commentary" ? { ref: item.id, segment: item.segment } : { ref: item.id };
}

/** Lines in the feed (newest first) that have not been seen yet, returned oldest first. */
export function unseenLines(feed: readonly TickerItem[], seen: ReadonlySet<string>): TickerItem[] {
  return feed.filter((item) => !seen.has(item.id)).reverse();
}
