# Rate Limiting Sample

> Runnable Python sample demonstrating production rate limiting patterns with Valkey.

## Prerequisites

- Docker or Podman
- Python 3.9+

## Quick Start

```bash
# 1. Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey:8.1.1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the demo
python main.py
```

## Expected Output

```text
=== Rate Limiting with Valkey — Demo ===

--- Pattern 1: Fixed-Window Rate Limiter ---
  [ALLOW] Request 1: 1/10
  [ALLOW] Request 2: 2/10
  ...
  [ALLOW] Request 10: 10/10
  [DENY] Request 11: 11/10
  [DENY] Request 12: 12/10

--- Pattern 2: Token-Aware Limiting ---
  [ALLOW] 100 tokens: used=0
  [ALLOW] 5000 tokens: used=100
  [ALLOW] 50000 tokens: used=5100
  [DENY] 60000 tokens: used=55100

--- Pattern 3: Dual Limiting ---
  Requests: 1/60, Tokens: 500/100000
  Allowed: True, Blocked by: None

--- Pattern 4: Hierarchical Limiting ---
  Allowed: True, Blocked by: None

--- Pattern 5: Budget-Based Limiting ---
  Allowed: True, Remaining: $0.07
  Allowed: False, Remaining: $0.07

=== Demo Complete ===
```

## Running Tests

```bash
python -m pytest test_rate_limiter.py -v
```

Tests run against a local Valkey instance and verify:

- Fixed-window counter behavior (allow/deny boundary)
- Token-aware limiting with rollback on rejection
- Dual limiting (request + token limits)
- Lua token bucket (burst, exhaustion, refill)
- Hierarchical multi-tier cascading checks
- Budget-based limiting with INCRBYFLOAT
- Concurrent agent slots with Sorted Set expiration

No external APIs or paid services needed — tests use deterministic inputs only.

## Teardown

```bash
docker stop valkey && docker rm valkey
```
