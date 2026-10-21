/**
 * Hook following the producer console state for a session, with actions to hold and release overlays.
 * State is pushed by the server as events whenever it changes; if the stream cannot be used, it falls back to
 * polling so the console keeps working behind proxies that block streaming. Errors are surfaced for display.
 */
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, producerStreamUrl } from "../../api/client";
import type { ProducerSummary } from "../../types";

/** Polling interval used only when the event stream is unavailable. */
const FALLBACK_POLL_MS = 2000;

export function useProducer(sessionId: string) {
  const [summary, setSummary] = useState<ProducerSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSummary(await api.producer(sessionId));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Producer console unavailable");
    }
  }, [sessionId]);

  useEffect(() => {
    let poll: number | undefined;
    const fallBack = () => {
      source.close();
      if (poll !== undefined) return;
      void refresh();
      poll = window.setInterval(() => void refresh(), FALLBACK_POLL_MS);
    };
    const source = new EventSource(producerStreamUrl(sessionId));
    source.addEventListener("summary", (message) => {
      setSummary(JSON.parse((message as MessageEvent<string>).data) as ProducerSummary);
      setError(null);
    });
    source.addEventListener("end", () => source.close());
    source.onerror = fallBack;
    return () => {
      source.close();
      window.clearInterval(poll);
    };
  }, [sessionId, refresh]);

  const hold = useCallback(async (on: boolean) => { await api.hold(sessionId, on); await refresh(); }, [sessionId, refresh]);
  const release = useCallback(async (momentId: string | null) => {
    await api.release(sessionId, momentId);
    await refresh();
  }, [sessionId, refresh]);

  return { summary, error, hold, release };
}
