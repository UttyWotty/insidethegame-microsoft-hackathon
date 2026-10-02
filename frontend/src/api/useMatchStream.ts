/**
 * React hook subscribing to a session's personalized server-sent event stream.
 * It resets and reconnects whenever the viewer's preferences change, and closes on unmount or match end.
 * Messages are folded into state by the pure matchReducer.
 */
import { useEffect, useReducer, useState } from "react";
import { initialMatchState, matchReducer, type MatchState, type MessageName } from "../state/matchState";
import type { ViewerSettings } from "../types";
import { streamUrl } from "./client";

const MESSAGE_NAMES: MessageName[] = ["match", "event", "snapshot", "cue", "recap", "end"];

export type ConnectionStatus = "connecting" | "open" | "ended" | "error";

export function useMatchStream(sessionId: string | null, viewer: ViewerSettings): [MatchState, ConnectionStatus] {
  const [state, dispatch] = useReducer(matchReducer, initialMatchState);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const { persona, language, team, player } = viewer;

  useEffect(() => {
    if (!sessionId) return undefined;
    dispatch({ type: "reset" });
    setStatus("connecting");
    const source = new EventSource(streamUrl(sessionId, { persona, language, team, player }));
    source.onopen = () => setStatus("open");
    source.onerror = () => setStatus((current) => (current === "ended" ? current : "error"));
    for (const name of MESSAGE_NAMES) {
      source.addEventListener(name, (message) => {
        dispatch({ type: "message", name, data: JSON.parse((message as MessageEvent<string>).data), receivedAt: Date.now() });
        if (name === "end") {
          setStatus("ended");
          source.close();
        }
      });
    }
    return () => source.close();
  }, [sessionId, persona, language, team, player]);

  return [state, status];
}
