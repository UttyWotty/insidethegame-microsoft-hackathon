/**
 * Tests for holding auto replays while a recap dialog is open.
 * A replay that comes due while the dialog is open stays queued and rolls when it closes, the queue's staleness rule
 * still drops replays more than 10 match minutes behind live, and a replay already rolling is not interrupted.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  emptyReplayQueue, holdsRecap, recapClosed, recapOpened, REPLAY_MAX_LAG_MATCH_S, replayDue, replayFinished,
  replayScheduled, type ReplayQueue,
} from "./replayQueue";
import type { ShotTrace } from "../state/matchState";

const shot = (id: string, result: string, second: number): ShotTrace => ({
  id, from: { x: 90, y: 30 }, to: { x: 105, y: 34 }, xg: 0.4, result, side: "home", at: 0, period: 2, second,
  shooter: "h9", card: null,
});
const ids = (state: ReplayQueue): [string | null, string[]] => [state.current?.id ?? null, state.queue.map((s) => s.id)];
const due = (state: ReplayQueue, next: ShotTrace): ReplayQueue => replayDue(replayScheduled(state), next);

describe("replays while a recap dialog is open", () => {
  it("keeps a replay that comes due while the dialog is open queued, and rolls it when the dialog closes", () => {
    const open = due(recapOpened(emptyReplayQueue), shot("save", "saved", 2820));
    expect(ids(open)).toEqual([null, ["save"]]);
    expect(open.pending).toBe(0);
    const closed = recapClosed(open, 3080);
    expect(ids(closed)).toEqual(["save", []]);
    expect(closed.recapOpen).toBe(false);
  });

  it("drops a replay that went stale while the dialog was open, goals included", () => {
    const open = due(due(recapOpened(emptyReplayQueue), shot("a", "goal", 2800)), shot("b", "saved", 3000));
    expect(ids(recapClosed(open, 2801 + REPLAY_MAX_LAG_MATCH_S))).toEqual(["b", []]);
    expect(ids(recapClosed(open, 3001 + REPLAY_MAX_LAG_MATCH_S))).toEqual([null, []]);
    expect(ids(recapClosed(open, null))).toEqual(["a", ["b"]]);
  });

  it("lets a replay already rolling finish, then holds the queue until the dialog closes", () => {
    const rolling = due(emptyReplayQueue, shot("a", "goal", 2700));
    const open = due(recapOpened(rolling), shot("b", "saved", 2760));
    expect(ids(open)).toEqual(["a", ["b"]]);
    const finished = replayFinished(open, 2800);
    expect(ids(finished)).toEqual([null, ["b"]]);
    expect(ids(recapClosed(finished, 2850))).toEqual(["b", []]);
  });

  it("applies staleness when a replay ends under an open dialog", () => {
    const open = due(recapOpened(due(emptyReplayQueue, shot("a", "goal", 2700))), shot("b", "saved", 2710));
    expect(ids(replayFinished(open, 2711 + REPLAY_MAX_LAG_MATCH_S))).toEqual([null, []]);
  });

  it("closing the dialog leaves a rolling replay and its queue alone", () => {
    const open = due(recapOpened(due(emptyReplayQueue, shot("a", "goal", 2700))), shot("b", "saved", 2710));
    const closed = recapClosed(replayFinished(recapClosed(open, 2720), 2730), 2740);
    expect(ids(recapClosed(open, 2720))).toEqual(["a", ["b"]]);
    expect(ids(closed)).toEqual(["b", []]);
  });

  it("rolls due replays at once again after the dialog closed with nothing queued", () => {
    const reopened = recapClosed(recapOpened(emptyReplayQueue), 2700);
    expect(ids(reopened)).toEqual([null, []]);
    expect(ids(due(reopened, shot("a", "goal", 2710)))).toEqual(["a", []]);
  });

  it("still holds a newly arriving recap while a replay waits behind the open dialog", () => {
    const open = due(recapOpened(emptyReplayQueue), shot("a", "goal", 2700));
    expect(holdsRecap(open)).toBe(true);
    expect(holdsRecap(recapOpened(emptyReplayQueue))).toBe(false);
  });
});
