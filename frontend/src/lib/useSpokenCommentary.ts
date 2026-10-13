/**
 * React hook that reads live commentary aloud with the browser's speech synthesis, in the viewer's language.
 * It is the thin I/O adapter around the pure planner in speech.ts: new feed lines are queued, spoken one at a time,
 * and the queue is cleared whenever voice is toggled or the language changes, so nothing stale is read out.
 */
import { useCallback, useEffect, useRef } from "react";
import type { TickerItem } from "../state/matchState";
import { SPEECH_RATE, enqueueSpeech, isSpeakable, pickVoice, unseenLines } from "./speech";

/** True when this browser can speak; the voice toggle is hidden otherwise. */
export const speechSupported: boolean =
  typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

export function useSpokenCommentary(feed: TickerItem[], language: string, enabled: boolean): void {
  const seen = useRef(new Set<string>());
  const queue = useRef<TickerItem[]>([]);
  const speaking = useRef(false);
  const generation = useRef(0);

  const speakNext = useCallback(() => {
    if (speaking.current || !queue.current.length) return;
    const [item, ...rest] = queue.current;
    queue.current = rest;
    const utterance = new SpeechSynthesisUtterance(item.text);
    const voice = pickVoice(window.speechSynthesis.getVoices(), language);
    if (voice) utterance.voice = voice;
    utterance.lang = voice?.lang ?? language;
    utterance.rate = SPEECH_RATE;
    const mine = generation.current;
    const done = () => {
      if (mine !== generation.current) return;
      speaking.current = false;
      speakNext();
    };
    utterance.onend = done;
    utterance.onerror = done;
    speaking.current = true;
    window.speechSynthesis.speak(utterance);
  }, [language]);

  // Reset only when voice is toggled or the language changes; feed updates are handled by the next effect.
  useEffect(() => {
    if (!speechSupported) return;
    generation.current += 1;
    seen.current = new Set(feed.map((item) => item.id));
    queue.current = [];
    speaking.current = false;
    window.speechSynthesis.cancel();
    return () => window.speechSynthesis.cancel();
  }, [enabled, language]);

  useEffect(() => {
    if (!speechSupported || !enabled) return;
    const fresh = unseenLines(feed, seen.current);
    fresh.forEach((item) => seen.current.add(item.id));
    queue.current = enqueueSpeech(queue.current, fresh.filter((item) => isSpeakable(item, language)));
    speakNext();
  }, [feed, enabled, language, speakNext]);
}
