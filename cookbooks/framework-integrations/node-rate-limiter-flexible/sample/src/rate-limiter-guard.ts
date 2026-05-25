import type { RateLimiterRes } from "rate-limiter-flexible";

/** Type guard for RateLimiterRes thrown by rate-limiter-flexible on limit exceeded. */
export function isRateLimiterRes(val: unknown): val is RateLimiterRes {
  return val !== null && typeof val === "object" && "msBeforeNext" in val;
}
