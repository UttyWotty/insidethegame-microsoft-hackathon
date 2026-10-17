/**
 * QA tests for the recap hold combined with turning Auto replays off and on while a recap dialog is open.
 * Turning replays off clears the held queue but keeps the dialog flag, so replays that come due after turning them
 * back on still wait for the dialog to close, and closing it with an empty queue rolls nothing.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import {
  emptyReplayQueue, holdsRecap, recapClosed, recapOpened, replayDue, replaysOff, replayScheduled, type ReplayQueue,
} from "./replayQueue";
import type { ShotTrace } from "../state/matchState";

const shot = (id: string, second: number): ShotTrace => ({
  id, from: { x: 90, y: 30 }, to: { x: 105, y: 34 }, xg: 0.4, result: "saved", side: "home", at: 0, period: 2,
  second, shooter: "h9", card: null,
});
const ids = (state: ReplayQueue): [string | null, string[]] => [state.current?.id ?? null, state.queue.map((s) => s.id)];

describe("Auto replays toggled while a recap dialog is open", () => {
  it("clears the held queue when turned off, and nothing rolls when the dialog closes", () => {
    const held = replayDue(replayScheduled(recapOpened(emptyReplayQueue)), shot("save", 2780));
    const off = replaysOff(held);
    expect(ids(off)).toEqual([null, []]);
    expect(off.recapOpen).toBe(true);
    expect(holdsRecap(off)).toBe(false);
    expect(ids(recapClosed(off, 2800))).toEqual([null, []]);
  });

  it("still holds a replay that comes due after turning replays back on until the dialog closes", () => {
    const back = replayDue(replayScheduled(replaysOff(recapOpened(emptyReplayQueue))), shot("late", 2900));
    expect(ids(back)).toEqual([null, ["late"]]);
    expect(ids(recapClosed(back, 2920))).toEqual(["late", []]);
  });

  it("opening the dialog twice and closing it once releases the queue", () => {
    const twice = replayDue(replayScheduled(recapOpened(recapOpened(emptyReplayQueue))), shot("a", 3000));
    expect(ids(recapClosed(twice, 3010))).toEqual(["a", []]);
  });
});
