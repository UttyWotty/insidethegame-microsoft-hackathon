/**
 * React hook that reads live commentary aloud in the viewer's language, preferring Azure AI Speech when available.
 * It is the thin I/O adapter around the pure planner in speech.ts: new feed lines are queued and spoken one at a
 * time, as neural audio from the server when it holds the line, otherwise (or on failure) with browser speech.
 */
import { useCallback, useEffect, useRef } from "react";
import type { TickerItem } from "../state/matchState";
import { SPEECH_RATE, enqueueSpeech, isSpeakable, pickVoice, serverSpeechRef, unseenLines } from "./speech";

/** True when this browser can speak on-device. */
export const speechSupported: boolean =
  typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

/** Builds the URL of server-voiced audio for a line, or null when neural speech is not available. */
export type SpeechUrlBuilder = ((ref: string, segment?: string) => string) | null;

export function useSpokenCommentary(feed: TickerItem[], language: string, enabled: boolean,
                                    serverUrl: SpeechUrlBuilder = null): void {
  const seen = useRef(new Set<string>());
  const queue = useRef<TickerItem[]>([]);
  const speaking = useRef(false);
  const generation = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);

  const speakLocally = useCallback((item: TickerItem, done: () => void) => {
    if (!speechSupported) return done();
    const utterance = new SpeechSynthesisUtterance(item.text);
    const voice = pickVoice(window.speechSynthesis.getVoices(), language);
    if (voice) utterance.voice = voice;
    utterance.lang = voice?.lang ?? language;
    utterance.rate = SPEECH_RATE;
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.speak(utterance);
  }, [language]);

  const speakNext = useCallback(() => {
    if (speaking.current || !queue.current.length) return;
    const [item, ...rest] = queue.current;
    queue.current = rest;
    const mine = generation.current;
    const done = () => {
      if (mine !== generation.current) return;
      speaking.current = false;
      speakNext();
    };
    speaking.current = true;
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
  }, [serverUrl, speakLocally]);

  // Reset only when voice is toggled, the language changes, or the speech source changes. The feed is read here
  // only to mark existing lines as seen; its updates are handled by the next effect.
  useEffect(() => {
    generation.current += 1;
    seen.current = new Set(feed.map((item) => item.id));
    queue.current = [];
    speaking.current = false;
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
    queue.current = enqueueSpeech(queue.current, fresh.filter((item) => isSpeakable(item, language)));
    speakNext();
  }, [feed, enabled, language, speakNext]);
}
