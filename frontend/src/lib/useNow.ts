/**
 * React hook returning the current wall-clock time, refreshed on a fixed interval.
 * Overlays use it to expire cues after their display duration.
 * The interval is coarse to avoid unnecessary re-renders.
 */
import { useEffect, useState } from "react";

const TICK_MS = 500;

export function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(id);
  }, []);
  return now;
}
