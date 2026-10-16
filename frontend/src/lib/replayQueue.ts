/**
 * Pure queue rules for auto replays: a qualifying replay that comes due while another rolls waits in a short queue
 * instead of being dropped, goals win a full queue, and stale entries are skipped so the broadcast stays near live.
 * It also tracks replays scheduled but not yet due, so a recap dialog can be held until no replay is pending.
 * backend/src/insidegame/datasets/demo_story.py mirrors these rules (REPLAY_QUEUE_MAX, REPLAY_MAX_LAG_MATCH_S).
 */
import type { ShotTrace } from "../state/matchState";

/** At most this many replays wait behind the one rolling; more would leave the broadcast far behind live. */
export const REPLAY_QUEUE_MAX = 2;
/** A queued replay is skipped (goals included) when its shot is more than this many match seconds behind live. */
export const REPLAY_MAX_LAG_MATCH_S = 600;
const GOAL_RESULT = "goal";

/** The replay on screen, the replays waiting behind it, and how many qualifying shots are not yet due. */
export interface ReplayQueue {
  current: ShotTrace | null;
  queue: ShotTrace[];
  pending: number;
}

/** No replay rolling, none queued, none scheduled. */
export const emptyReplayQueue: ReplayQueue = { current: null, queue: [], pending: 0 };

function isGoal(shot: ShotTrace): boolean {
  return shot.result === GOAL_RESULT;
}

/** A qualifying shot's replay was scheduled; it counts as pending until it comes due. */
export function replayScheduled(state: ReplayQueue): ReplayQueue {
  return { ...state, pending: state.pending + 1 };
}

/** Add a shot to a queue under the cap: a goal replaces the oldest non-goal when full, a non-goal is dropped. */
export function enqueueReplay(queue: ShotTrace[], shot: ShotTrace): ShotTrace[] {
  if (queue.length < REPLAY_QUEUE_MAX) return [...queue, shot];
  if (!isGoal(shot)) return queue;
  const oldest = queue.findIndex((queued) => !isGoal(queued));
  return oldest < 0 ? queue : [...queue.slice(0, oldest), ...queue.slice(oldest + 1), shot];
}

/** A scheduled replay came due: it rolls at once when the screen is free, otherwise it joins the queue. */
export function replayDue(state: ReplayQueue, shot: ShotTrace): ReplayQueue {
  const pending = Math.max(0, state.pending - 1);
  if (state.current === null) return { ...state, current: shot, pending };
  return { ...state, queue: enqueueReplay(state.queue, shot), pending };
}

/** Whether a queued shot is still close enough to the live match second to be worth replaying. */
export function isFresh(shot: ShotTrace, liveSecond: number): boolean {
  return liveSecond - shot.second <= REPLAY_MAX_LAG_MATCH_S;
}

/**
 * The rolling replay ended or the viewer pressed "Back to live": the next fresh queued replay rolls, stale ones
 * are dropped. With no live clock yet (null), nothing counts as stale.
 */
export function replayFinished(state: ReplayQueue, liveSecond: number | null): ReplayQueue {
  const fresh = liveSecond === null ? state.queue : state.queue.filter((shot) => isFresh(shot, liveSecond));
  const [next = null, ...rest] = fresh;
  return { ...state, current: next, queue: rest };
}

/** Auto replays turned off: the queue and the pending count clear; a replay already on screen finishes. */
export function replaysOff(state: ReplayQueue): ReplayQueue {
  return { ...state, queue: [], pending: 0 };
}

/** Whether an arriving recap must wait: a replay is rolling, queued, or scheduled and not yet due. */
export function holdsRecap(state: ReplayQueue): boolean {
  return state.current !== null || state.queue.length > 0 || state.pending > 0;
}
