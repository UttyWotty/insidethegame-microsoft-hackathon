/**
 * Retry helper with exponential backoff for calls that can fail transiently, such as a backend cold start.
 * The sleep function is injected so the behaviour is testable without real timers.
 * After the last attempt the original error is rethrown for the caller to display.
 */
export const DEFAULT_ATTEMPTS = 5;
export const DEFAULT_BASE_DELAY_MS = 500;
const BACKOFF_FACTOR = 2;

export type Sleep = (ms: number) => Promise<void>;
export const realSleep: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function withRetry<T>(
  call: () => Promise<T>,
  attempts: number = DEFAULT_ATTEMPTS,
  baseDelayMs: number = DEFAULT_BASE_DELAY_MS,
  sleep: Sleep = realSleep,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await call();
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await sleep(baseDelayMs * BACKOFF_FACTOR ** attempt);
    }
  }
  throw lastError;
}
