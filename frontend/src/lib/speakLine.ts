/**
 * Thin browser-speech adapter that speaks one line immediately, cancelling anything already being said.
 * Used by the highlights reel, which narrates one clip at a time rather than following a live feed.
 * It reuses the live commentary's voice choice and excitement so both sound like the same commentator.
 */
import type { Intensity } from "../state/matchState";
import { deliveryFor, pickVoice } from "./speech";
import { speechSupported } from "./useSpokenCommentary";

/** Speak text in a language with the given energy at a replay speed; a no-op where speech is unsupported. */
export function speakLine(text: string, language: string, intensity: Intensity, speed: number): void {
  if (!speechSupported) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = pickVoice(window.speechSynthesis.getVoices(), language);
  if (voice) utterance.voice = voice;
  utterance.lang = voice?.lang ?? language;
  const delivery = deliveryFor(intensity, speed);
  utterance.rate = delivery.rate;
  utterance.pitch = delivery.pitch;
  window.speechSynthesis.speak(utterance);
}

/** Stop any speech in progress. */
export function stopSpeaking(): void {
  if (speechSupported) window.speechSynthesis.cancel();
}
