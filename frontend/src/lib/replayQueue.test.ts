/**
 * Tests for the auto-replay queue rules.
 * They cover queueing while a replay rolls, the cap with goal priority, staleness on dequeue, Auto replays off,
 * skipping the current replay, and holding a recap while a replay is rolling, queued, or scheduled. All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  emptyReplayQueue, enqueueReplay, holdsRecap, REPLAY_MAX_LAG_MATCH_S, REPLAY_QUEUE_MAX, replayDue, replayFinished,
  replaysOff, replayScheduled, type ReplayQueue,
} from "./replayQueue";
import type { ShotTrace } from "../state/matchState";

const shot = (id: string, result: string, second: number): ShotTrace => ({
  id, from: { x: 90, y: 30 }, to: { x: 105, y: 34 }, xg: 0.4, result, side: "home", at: 0, period: 1, second,
  shooter: "h9", card: null,
});
const ids = (state: ReplayQueue): [string | null, string[]] => [state.current?.id ?? null, state.queue.map((s) => s.id)];
/** Schedule then bring due each shot in order, as the broadcast timers do. */
const dueAll = (state: ReplayQueue, shots: ShotTrace[]): ReplayQueue =>
  shots.reduce((s, next) => replayDue(replayScheduled(s), next), state);

describe("replay queue", () => {
  it("rolls a replay at once when the screen is free and queues one that comes due while another rolls", () => {
    const first = dueAll(emptyReplayQueue, [shot("a", "goal", 1680)]);
    expect(ids(first)).toEqual(["a", []]);
    const second = dueAll(first, [shot("b", "goal", 2040)]);
    expect(ids(second)).toEqual(["a", ["b"]]);
    expect(ids(replayFinished(second, 2100))).toEqual(["b", []]);
    expect(ids(replayFinished(replayFinished(second, 2100), 2400))).toEqual([null, []]);
  });

  it("caps the queue; a goal replaces the oldest non-goal when it is full", () => {
    expect(REPLAY_QUEUE_MAX).toBe(2);
    const full = dueAll(emptyReplayQueue, [shot("a", "saved", 100), shot("b", "goal", 110), shot("c", "saved", 120)]);
    expect(ids(full)).toEqual(["a", ["b", "c"]]);
    expect(ids(dueAll(full, [shot("d", "goal", 130)]))).toEqual(["a", ["b", "d"]]);
    const noMiss = enqueueReplay([shot("b", "goal", 110), shot("c", "goal", 120)], shot("d", "goal", 130));
    expect(noMiss.map((s) => s.id)).toEqual(["b", "c"]);
  });

  it("drops a non-goal that arrives at a full queue", () => {
    const full = dueAll(emptyReplayQueue, [shot("a", "saved", 100), shot("b", "saved", 110), shot("c", "saved", 120)]);
    expect(ids(dueAll(full, [shot("d", "off_target", 130)]))).toEqual(["a", ["b", "c"]]);
  });

  it("drops stale queued replays on dequeue, goals included", () => {
    const queued = dueAll(emptyReplayQueue, [shot("a", "saved", 1000), shot("b", "goal", 1010), shot("c", "saved", 1500)]);
    expect(ids(replayFinished(queued, 1010 + REPLAY_MAX_LAG_MATCH_S))).toEqual(["b", ["c"]]);
    expect(ids(replayFinished(queued, 1011 + REPLAY_MAX_LAG_MATCH_S))).toEqual(["c", []]);
    expect(ids(replayFinished(queued, 1501 + REPLAY_MAX_LAG_MATCH_S))).toEqual([null, []]);
    expect(ids(replayFinished(queued, null))).toEqual(["b", ["c"]]);
  });

  it("clears the queue and pending count when Auto replays is turned off, leaving the rolling replay", () => {
    const busy = replayScheduled(dueAll(emptyReplayQueue, [shot("a", "goal", 100), shot("b", "goal", 110)]));
    const off = replaysOff(busy);
    expect(ids(off)).toEqual(["a", []]);
    expect(off.pending).toBe(0);
  });

  it("skipping the current replay (Back to live) continues with the queue", () => {
    const busy = dueAll(emptyReplayQueue, [shot("a", "goal", 100), shot("b", "saved", 110), shot("c", "goal", 120)]);
    const skipped = replayFinished(busy, 130);
    expect(ids(skipped)).toEqual(["b", ["c"]]);
  });

  it("holds a recap while a replay is rolling, queued, or scheduled, and releases it when all are empty", () => {
    expect(holdsRecap(emptyReplayQueue)).toBe(false);
    const scheduled = replayScheduled(emptyReplayQueue);
    expect(holdsRecap(scheduled)).toBe(true);
    const rolling = replayDue(scheduled, shot("a", "goal", 5400));
    expect(holdsRecap(rolling)).toBe(true);
    const queued = dueAll(rolling, [shot("b", "goal", 5410)]);
    expect(holdsRecap(queued)).toBe(true);
    const next = replayFinished(queued, 5420);
    expect(holdsRecap(next)).toBe(true);
    expect(holdsRecap(replayFinished(next, 5430))).toBe(false);
  });

  it("keeps the pending count at zero when a replay comes due after Auto replays off cleared it", () => {
    const off = replaysOff(replayScheduled(emptyReplayQueue));
    const late = replayDue(off, shot("a", "goal", 100));
    expect(late.pending).toBe(0);
    expect(holdsRecap(replayFinished(late, 120))).toBe(false);
  });

  it("does not count a first-half stoppage-time shot as stale when the second half restarts at 45:00", () => {
    const queued = dueAll(emptyReplayQueue, [shot("a", "saved", 2820), shot("b", "goal", 2850)]);
    expect(ids(replayFinished(queued, 2700))).toEqual(["b", []]);
  });

  it("drops a non-goal at a full queue of goals and keeps the queue order on dequeue", () => {
    const full = dueAll(emptyReplayQueue, [shot("a", "saved", 100), shot("b", "goal", 110), shot("c", "goal", 120)]);
    expect(ids(dueAll(full, [shot("d", "saved", 130), shot("e", "saved", 140)]))).toEqual(["a", ["b", "c"]]);
    expect(ids(replayFinished(full, 200))).toEqual(["b", ["c"]]);
  });
});
