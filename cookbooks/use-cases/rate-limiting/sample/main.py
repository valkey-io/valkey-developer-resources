"""Rate Limiting with Valkey — Demo Script.

Demonstrates fixed-window, token-aware, dual limiting, token bucket,
hierarchical limiting, and budget-based rate limiting using Valkey.

Requirements:
    - Valkey running on localhost:6379
"""

import time
from dataclasses import dataclass

import valkey

# --- Configuration ---
VALKEY_HOST = "localhost"
VALKEY_PORT = 6379

# --- Client ---
client = valkey.Valkey(
    host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=5.0
)


# =============================================================================
# Pattern 1: Fixed-Window Rate Limiter
# =============================================================================


def check_rate_limit(
    user_id: str, max_requests: int = 10, window: int = 60
) -> dict:
    """Fixed-window rate limiter using INCR + EXPIRE."""
    window_num = int(time.time() // window)
    key = f"rl:{user_id}:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, window)
    results = pipe.execute()

    current = results[0]
    allowed = current <= max_requests

    return {
        "allowed": allowed,
        "current": current,
        "limit": max_requests,
        "remaining": max(0, max_requests - current),
    }


# =============================================================================
# Pattern 2: Token-Aware Limiting
# =============================================================================


def check_token_limit(
    identifier: str,
    input_tokens: int,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Rate limit by token consumption per window."""
    window_num = int(time.time() // window)
    key = f"tl:{identifier}:tok:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.get(key)
    pipe.incrby(key, input_tokens)
    pipe.expire(key, window)
    results = pipe.execute()

    current_before = int(results[0] or 0)
    allowed = current_before + input_tokens <= max_tokens

    if not allowed:
        client.decrby(key, input_tokens)

    return {
        "allowed": allowed,
        "tokens_used": current_before,
        "tokens_remaining": max(0, max_tokens - current_before),
        "max_tokens": max_tokens,
    }


# =============================================================================
# Pattern 3: Dual Limiting (Requests + Tokens)
# =============================================================================


def dual_limit_check(
    identifier: str,
    tokens: int,
    max_requests: int = 60,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Limit by both request count AND token count."""
    window_num = int(time.time() // window)
    req_key = f"dl:{identifier}:req:{window_num}"
    tok_key = f"dl:{identifier}:tok:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(req_key)
    pipe.expire(req_key, window)
    pipe.incrby(tok_key, tokens)
    pipe.expire(tok_key, window)
    results = pipe.execute()

    req_count = results[0]
    tok_count = results[2]

    req_ok = req_count <= max_requests
    tok_ok = tok_count <= max_tokens
    allowed = req_ok and tok_ok

    blocked_by = None
    if not req_ok:
        blocked_by = "requests"
    elif not tok_ok:
        blocked_by = "tokens"

    return {
        "allowed": allowed,
        "blocked_by": blocked_by,
        "requests": f"{req_count}/{max_requests}",
        "tokens": f"{tok_count}/{max_tokens}",
    }


# =============================================================================
# Pattern 4: Hierarchical Rate Limiting
# =============================================================================


@dataclass
class Tier:
    name: str
    identifier: str
    max_requests: int
    max_tokens: int
    window_seconds: int


def hierarchical_check(tiers: list, tokens: int) -> dict:
    """Check all tiers in 2 round-trips regardless of tier count."""
    now = time.time()

    # Phase 1: Read all counters in one pipeline
    pipe = client.pipeline(transaction=False)
    for tier in tiers:
        window_num = int(now // tier.window_seconds)
        pipe.get(f"hier:{tier.name}:{tier.identifier}:req:{window_num}")
        pipe.get(f"hier:{tier.name}:{tier.identifier}:tok:{window_num}")
    results = pipe.execute()

    # Phase 2: Check each tier
    blocked_by = None
    for i, tier in enumerate(tiers):
        current_req = int(results[i * 2] or 0)
        current_tok = int(results[i * 2 + 1] or 0)
        if current_req + 1 > tier.max_requests or current_tok + tokens > tier.max_tokens:
            blocked_by = tier.name
            break

    # Phase 3: If allowed, increment all tiers atomically
    if not blocked_by:
        pipe = client.pipeline(transaction=True)
        for tier in tiers:
            window_num = int(now // tier.window_seconds)
            req_key = f"hier:{tier.name}:{tier.identifier}:req:{window_num}"
            tok_key = f"hier:{tier.name}:{tier.identifier}:tok:{window_num}"
            pipe.incr(req_key)
            pipe.expire(req_key, tier.window_seconds)
            pipe.incrby(tok_key, tokens)
            pipe.expire(tok_key, tier.window_seconds)
        pipe.execute()

    return {"allowed": blocked_by is None, "blocked_by": blocked_by}


# =============================================================================
# Pattern 5: Budget-Based Limiting
# =============================================================================


def check_budget(
    identifier: str, estimated_cost: float, budget: float = 10.00, window: int = 3600
) -> dict:
    """Check if a request fits within the dollar budget."""
    window_num = int(time.time() // window)
    key = f"budget:{identifier}:{window_num}"

    current = float(client.get(key) or 0)

    if current + estimated_cost <= budget:
        client.incrbyfloat(key, estimated_cost)
        client.expire(key, window)
        return {"allowed": True, "remaining": round(budget - current - estimated_cost, 4)}
    else:
        return {"allowed": False, "remaining": round(max(0, budget - current), 4)}


# =============================================================================
# Demo
# =============================================================================


def main():
    print("=== Rate Limiting with Valkey — Demo ===\n")

    # --- Fixed-window ---
    print("--- Pattern 1: Fixed-Window Rate Limiter ---")
    for i in range(12):
        result = check_rate_limit("demo-user", max_requests=10)
        status = "ALLOW" if result["allowed"] else "DENY"
        print(f"  [{status}] Request {i+1}: {result['current']}/{result['limit']}")
    print()

    # --- Token-aware ---
    print("--- Pattern 2: Token-Aware Limiting ---")
    for tokens in [100, 5000, 50000, 60000]:
        result = check_token_limit("demo-user", input_tokens=tokens)
        status = "ALLOW" if result["allowed"] else "DENY"
        print(f"  [{status}] {tokens} tokens: used={result['tokens_used']}")
    print()

    # --- Dual limiting ---
    print("--- Pattern 3: Dual Limiting ---")
    result = dual_limit_check("demo-user", tokens=500)
    print(f"  Requests: {result['requests']}, Tokens: {result['tokens']}")
    print(f"  Allowed: {result['allowed']}, Blocked by: {result['blocked_by']}")
    print()

    # --- Hierarchical ---
    print("--- Pattern 4: Hierarchical Limiting ---")
    tiers = [
        Tier("org", "acme-corp", 10000, 1_000_000, 3600),
        Tier("team", "engineering", 5000, 500_000, 3600),
        Tier("user", "alice", 1000, 100_000, 3600),
        Tier("agent", "agent-1", 200, 25_000, 3600),
    ]
    result = hierarchical_check(tiers, tokens=500)
    print(f"  Allowed: {result['allowed']}, Blocked by: {result['blocked_by']}")
    print()

    # --- Budget ---
    print("--- Pattern 5: Budget-Based Limiting ---")
    result = check_budget("demo-user", estimated_cost=0.03, budget=0.10)
    print(f"  Allowed: {result['allowed']}, Remaining: ${result['remaining']}")
    result = check_budget("demo-user", estimated_cost=0.08, budget=0.10)
    print(f"  Allowed: {result['allowed']}, Remaining: ${result['remaining']}")
    print()

    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
