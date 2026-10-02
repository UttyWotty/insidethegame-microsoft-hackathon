/**
 * Hook polling the producer console state for a session, with actions to hold and release overlays.
 * Polling keeps the console simple and independent of any viewer segment's stream.
 * Errors, including a missing producer key, are surfaced for display.
 */
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { ProducerSummary } from "../../types";

const POLL_MS = 2000;

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
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  const hold = useCallback(async (on: boolean) => { await api.hold(sessionId, on); await refresh(); }, [sessionId, refresh]);
  const release = useCallback(async (momentId: string | null) => {
    await api.release(sessionId, momentId);
    await refresh();
  }, [sessionId, refresh]);

  return { summary, error, hold, release };
}
