/**
 * React hook that reads live commentary aloud in the viewer's language, preferring Azure AI Speech when available.
 * It is the thin I/O adapter around the pure planner in speech.ts: new feed lines are queued and spoken one at a
 * time, as neural audio from the server when it holds the line, otherwise (or on failure) with browser speech.
 * Lines that waited too long are skipped so speech stays with play, and close calls cut off calm lines. It waits
 * briefly after cancelling before speaking again and frees the queue if a line never reports its end, working
 * around browsers that drop or stall utterances.
 */
import { useCallback, useEffect, useRef } from "react";
import type { Intensity, TickerItem } from "../state/matchState";
import {
  deliveryFor, enqueueSpeech, interrupts, isSpeakable, isStale, latestSpeakable, pickVoice, serverSpeechRef,
  unseenLines, watchdogMs,
} from "./speech";

/** Pause after cancelling speech before speaking again; speaking immediately can be silently dropped. */
const CANCEL_SETTLE_MS = 120;

/** True when this browser can speak on-device. */
export const speechSupported: boolean =
  typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

/** Builds the URL of server-voiced audio for a line, or null when neural speech is not available. */
export type SpeechUrlBuilder = ((ref: string, segment?: string) => string) | null;

/** Speaks new feed lines; matchSpeed sets the pace, and serverUrl (default null) enables neural audio. */
export function useSpokenCommentary(feed: TickerItem[], language: string, enabled: boolean, matchSpeed: number,
                                    serverUrl: SpeechUrlBuilder = null): void {
  const seen = useRef(new Set<string>());
  const queue = useRef<TickerItem[]>([]);
  const speaking = useRef(false);
  const current = useRef<Intensity | null>(null);
  const arrived = useRef(new Map<string, number>());
  const generation = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);

  const speakLocally = useCallback((item: TickerItem, done: () => void) => {
    if (!speechSupported) return done();
    const utterance = new SpeechSynthesisUtterance(item.text);
    const voice = pickVoice(window.speechSynthesis.getVoices(), language);
    if (voice) utterance.voice = voice;
    utterance.lang = voice?.lang ?? language;
    const delivery = deliveryFor(item.intensity, matchSpeed);
    utterance.rate = delivery.rate;
    utterance.pitch = delivery.pitch;
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.speak(utterance);
  }, [language, matchSpeed]);

  const speakNext = useCallback(() => {
    if (speaking.current) return;
    const now = performance.now();
    queue.current = queue.current.filter((line) => !isStale(line.intensity, now - (arrived.current.get(line.id) ?? now)));
    if (!queue.current.length) return;
    const [item, ...rest] = queue.current;
    queue.current = rest;
    arrived.current.delete(item.id);
    const mine = generation.current;
    let finished = false;
    const done = () => {
      window.clearTimeout(watchdog);
      if (finished || mine !== generation.current) return;
      finished = true;
      speaking.current = false;
      current.current = null;
      speakNext();
    };
    const watchdog = window.setTimeout(done, watchdogMs(item.text, deliveryFor(item.intensity, matchSpeed).rate));
    speaking.current = true;
    current.current = item.intensity;
    const ref = serverUrl ? serverSpeechRef(item) : null;
    if (!serverUrl || !ref) return speakLocally(item, done);
    const player = new Audio(serverUrl(ref.ref, ref.segment));
    audio.current = player;
    let fellBack = false;
    const fallBack = () => {
      if (fellBack || mine !== generation.current) return;
      fellBack = true;
      speakLocally(item, done);
    };
    player.onended = done;
    player.onerror = fallBack;
    player.play().catch(fallBack);
  }, [serverUrl, speakLocally, matchSpeed]);

  // Reset only when voice is toggled, the language changes, or the speech source changes. Earlier lines are marked
  // as seen, except the newest speakable one, which is spoken at once; feed updates are handled by the next effect.
  useEffect(() => {
    generation.current += 1;
    const latest = latestSpeakable(feed, language);
    seen.current = new Set(feed.filter((item) => item !== latest).map((item) => item.id));
    queue.current = [];
    arrived.current.clear();
    speaking.current = false;
    current.current = null;
    const stop = () => {
      audio.current?.pause();
      audio.current = null;
      if (speechSupported) window.speechSynthesis.cancel();
    };
    stop();
    return stop;
  }, [enabled, language, serverUrl]);

  useEffect(() => {
    if (!enabled) return;
    const fresh = unseenLines(feed, seen.current);
    fresh.forEach((item) => seen.current.add(item.id));
    const speakable = fresh.filter((item) => isSpeakable(item, language));
    const now = performance.now();
    speakable.forEach((item) => arrived.current.set(item.id, now));
    if (interrupts(speakable, current.current)) {
      generation.current += 1;
      queue.current = [];
      speaking.current = false;
      current.current = null;
      audio.current?.pause();
      if (speechSupported) window.speechSynthesis.cancel();
      queue.current = enqueueSpeech([], speakable);
      window.setTimeout(speakNext, CANCEL_SETTLE_MS);
      return;
    }
    queue.current = enqueueSpeech(queue.current, speakable);
    speakNext();
  }, [feed, enabled, language, speakNext]);
}
