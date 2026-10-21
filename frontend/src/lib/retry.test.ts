/**
 * Tests for the exponential backoff retry helper.
 * Sleep is replaced by a recorder, so delays are asserted without waiting.
 * Both eventual success and final failure paths are covered.
 */
import { describe, expect, it } from "vitest";
import { withRetry } from "./retry";

describe("withRetry", () => {
  it("retries with exponential backoff until the call succeeds", async () => {
    const delays: number[] = [];
    let calls = 0;
    const result = await withRetry(async () => {
      calls += 1;
      if (calls < 3) throw new Error("not yet");
      return "ok";
    }, 5, 100, async (ms) => { delays.push(ms); });
    expect(result).toBe("ok");
    expect(delays).toEqual([100, 200]);
  });

  it("rethrows the last error after the final attempt", async () => {
    const delays: number[] = [];
    await expect(withRetry(async () => { throw new Error("down"); }, 3, 50, async (ms) => { delays.push(ms); }))
      .rejects.toThrow("down");
    expect(delays).toEqual([50, 100]);
  });
});
