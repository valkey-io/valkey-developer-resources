"""Tests for rate limiting patterns.

Requires:
    - Valkey running on localhost:6379

Tests verify the core rate-limiting logic using deterministic inputs.
No external APIs or paid services needed.
"""

import time
from dataclasses import dataclass

import pytest
import valkey

VALKEY_HOST = "localhost"
VALKEY_PORT = 6379


@pytest.fixture(scope="module")
def client():
    """Create a Valkey client and clean up test keys after tests."""
    c = valkey.Valkey(
        host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=5.0
    )
    assert c.ping(), "Valkey is not reachable"
    yield c
    # Cleanup all test keys
    for pattern in ["test_rl:*", "test_tl:*", "test_dl:*", "test_hier:*", "test_budget:*",
                    "test_bucket:*", "test_concurrent:*"]:
        for key in c.scan_iter(match=pattern):
            c.delete(key)


# =============================================================================
# Test: Fixed-Window Rate Limiter
# =============================================================================


class TestFixedWindow:
    """Test the basic fixed-window rate limiter."""

    def test_allows_within_limit(self, client):
        """Requests within the limit are allowed."""
        window_num = int(time.time() // 60)
        key = f"test_rl:user1:{window_num}"
        # Ensure clean state
        client.delete(key)

        for i in range(5):
            pipe = client.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, 60)
            results = pipe.execute()
            assert results[0] == i + 1
            assert results[0] <= 10  # Under limit

    def test_blocks_over_limit(self, client):
        """Requests over the limit are blocked."""
        window_num = int(time.time() // 60)
        key = f"test_rl:overlimit:{window_num}"
        client.delete(key)

        # Fill up to limit
        client.set(key, "10")
        client.expire(key, 60)

        # Next request exceeds
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, 60)
        results = pipe.execute()
        assert results[0] == 11
        assert results[0] > 10  # Over limit

    def test_window_isolation(self, client):
        """Different windows have independent counters."""
        key_a = "test_rl:isolation:1000"
        key_b = "test_rl:isolation:1001"
        client.delete(key_a, key_b)

        client.set(key_a, "10")
        client.set(key_b, "0")

        assert int(client.get(key_a)) == 10
        assert int(client.get(key_b)) == 0


# =============================================================================
# Test: Token-Aware Limiting
# =============================================================================


class TestTokenAware:
    """Test token-based rate limiting."""

    def test_allows_tokens_within_limit(self, client):
        """Token requests within the budget are allowed."""
        window_num = int(time.time() // 60)
        key = f"test_tl:tok_user:tok:{window_num}"
        client.delete(key)

        # Request 5000 tokens against 100k limit
        pipe = client.pipeline(transaction=True)
        pipe.get(key)
        pipe.incrby(key, 5000)
        pipe.expire(key, 60)
        results = pipe.execute()

        current_before = int(results[0] or 0)
        assert current_before + 5000 <= 100_000

    def test_blocks_tokens_over_limit(self, client):
        """Token requests exceeding the budget are blocked."""
        window_num = int(time.time() // 60)
        key = f"test_tl:tok_over:tok:{window_num}"
        client.delete(key)

        # Pre-fill to 95000 tokens
        client.set(key, "95000")
        client.expire(key, 60)

        # Request 10000 more — should exceed 100k limit
        current = int(client.get(key) or 0)
        assert current + 10000 > 100_000

    def test_rollback_on_reject(self, client):
        """Rejected token requests roll back the counter."""
        window_num = int(time.time() // 60)
        key = f"test_tl:rollback:tok:{window_num}"
        client.delete(key)

        # Set to 95000
        client.set(key, "95000")
        client.expire(key, 60)

        # Attempt 10000 (would exceed 100k)
        pipe = client.pipeline(transaction=True)
        pipe.get(key)
        pipe.incrby(key, 10000)
        pipe.expire(key, 60)
        results = pipe.execute()

        current_before = int(results[0] or 0)
        if current_before + 10000 > 100_000:
            # Rollback
            client.decrby(key, 10000)

        # Counter should be back to 95000
        assert int(client.get(key)) == 95000


# =============================================================================
# Test: Dual Limiting
# =============================================================================


class TestDualLimiting:
    """Test request + token dual limiting."""

    def test_allows_when_both_under(self, client):
        """Allowed when both request and token counts are within limits."""
        window_num = int(time.time() // 60)
        req_key = f"test_dl:dual:req:{window_num}"
        tok_key = f"test_dl:dual:tok:{window_num}"
        client.delete(req_key, tok_key)

        pipe = client.pipeline(transaction=True)
        pipe.incr(req_key)
        pipe.expire(req_key, 60)
        pipe.incrby(tok_key, 500)
        pipe.expire(tok_key, 60)
        results = pipe.execute()

        req_count = results[0]
        tok_count = results[2]
        assert req_count <= 60
        assert tok_count <= 100_000

    def test_blocks_on_request_limit(self, client):
        """Blocked when request count exceeds limit."""
        window_num = int(time.time() // 60)
        req_key = f"test_dl:reqblock:req:{window_num}"
        tok_key = f"test_dl:reqblock:tok:{window_num}"
        client.delete(req_key, tok_key)

        # Pre-fill requests to limit
        client.set(req_key, "60")
        client.expire(req_key, 60)

        pipe = client.pipeline(transaction=True)
        pipe.incr(req_key)
        pipe.expire(req_key, 60)
        pipe.incrby(tok_key, 100)
        pipe.expire(tok_key, 60)
        results = pipe.execute()

        req_count = results[0]
        assert req_count > 60  # Request limit exceeded

    def test_blocks_on_token_limit(self, client):
        """Blocked when token count exceeds limit."""
        window_num = int(time.time() // 60)
        req_key = f"test_dl:tokblock:req:{window_num}"
        tok_key = f"test_dl:tokblock:tok:{window_num}"
        client.delete(req_key, tok_key)

        # Pre-fill tokens to limit
        client.set(tok_key, "100000")
        client.expire(tok_key, 60)

        pipe = client.pipeline(transaction=True)
        pipe.incr(req_key)
        pipe.expire(req_key, 60)
        pipe.incrby(tok_key, 500)
        pipe.expire(tok_key, 60)
        results = pipe.execute()

        tok_count = results[2]
        assert tok_count > 100_000  # Token limit exceeded


# =============================================================================
# Test: Token Bucket (Lua Script)
# =============================================================================


TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, math.floor(tokens)}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    local wait = (requested - tokens) / refill_rate
    return {0, math.floor(tokens), math.ceil(wait * 1000)}
end
"""


class TestTokenBucket:
    """Test the Lua-based token bucket."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Load the Lua script and clean up."""
        self.client = client
        # Use a non-decode client for evalsha (Lua returns integers)
        self.raw_client = valkey.Valkey(
            host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=False, socket_timeout=5.0
        )
        self.sha = self.raw_client.script_load(TOKEN_BUCKET_SCRIPT)
        self.raw_client.delete(b"test_bucket:agent1")
        yield
        self.raw_client.delete(b"test_bucket:agent1")

    def test_first_request_allowed(self):
        """First request uses initial capacity — should be allowed."""
        now = time.time()
        result = self.raw_client.evalsha(
            self.sha, 1, "test_bucket:agent1", "50", "5.0", "1", str(now)
        )
        assert result[0] == 1  # Allowed
        assert result[1] == 49  # 50 - 1 = 49 remaining

    def test_exhaustion_blocks(self):
        """Requesting more than capacity blocks."""
        now = time.time()
        # Request all 50 tokens
        self.raw_client.evalsha(
            self.sha, 1, "test_bucket:agent1", "50", "5.0", "50", str(now)
        )
        # Next request should be denied
        result = self.raw_client.evalsha(
            self.sha, 1, "test_bucket:agent1", "50", "5.0", "1", str(now)
        )
        assert result[0] == 0  # Denied
        assert len(result) == 3  # Includes retry_after_ms

    def test_refill_over_time(self):
        """Tokens refill after time passes."""
        now = time.time()
        # Exhaust all tokens
        self.raw_client.evalsha(
            self.sha, 1, "test_bucket:agent1", "50", "5.0", "50", str(now)
        )
        # 2 seconds later at refill_rate=5.0 → 10 tokens refilled
        later = now + 2.0
        result = self.raw_client.evalsha(
            self.sha, 1, "test_bucket:agent1", "50", "5.0", "5", str(later)
        )
        assert result[0] == 1  # Allowed (10 refilled, 5 requested)
        assert result[1] == 5  # 10 - 5 = 5 remaining


# =============================================================================
# Test: Hierarchical Limiting
# =============================================================================


@dataclass
class Tier:
    name: str
    identifier: str
    max_requests: int
    max_tokens: int
    window_seconds: int


class TestHierarchical:
    """Test cascading multi-tier rate limiting."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Clean hierarchical test keys."""
        self.client = client
        for key in client.scan_iter(match="test_hier:*"):
            client.delete(key)
        yield
        for key in client.scan_iter(match="test_hier:*"):
            client.delete(key)

    def test_allows_when_all_tiers_under_limit(self):
        """Request allowed when all tiers are within limits."""
        tiers = [
            Tier("org", "test-org", 1000, 100_000, 3600),
            Tier("user", "test-user", 100, 10_000, 3600),
        ]
        result = self._hierarchical_check(tiers, tokens=500)
        assert result["allowed"] is True
        assert result["blocked_by"] is None

    def test_blocks_at_lowest_tier(self):
        """Request blocked by the most restrictive tier."""
        now = time.time()
        window_num = int(now // 3600)
        # Pre-fill user tier to its limit
        self.client.set(f"test_hier:user:test-user:req:{window_num}", "100")
        self.client.expire(f"test_hier:user:test-user:req:{window_num}", 3600)

        tiers = [
            Tier("org", "test-org", 1000, 100_000, 3600),
            Tier("user", "test-user", 100, 10_000, 3600),
        ]
        result = self._hierarchical_check(tiers, tokens=500)
        assert result["allowed"] is False
        assert result["blocked_by"] == "user"

    def test_blocks_at_token_limit(self):
        """Request blocked when token limit is hit at any tier."""
        now = time.time()
        window_num = int(now // 3600)
        # Pre-fill org token tier to its limit
        self.client.set(f"test_hier:org:test-org:tok:{window_num}", "100000")
        self.client.expire(f"test_hier:org:test-org:tok:{window_num}", 3600)

        tiers = [
            Tier("org", "test-org", 1000, 100_000, 3600),
            Tier("user", "test-user", 100, 10_000, 3600),
        ]
        result = self._hierarchical_check(tiers, tokens=500)
        assert result["allowed"] is False
        assert result["blocked_by"] == "org"

    def _hierarchical_check(self, tiers: list, tokens: int) -> dict:
        """Local implementation for testing with test key prefix."""
        now = time.time()

        pipe = self.client.pipeline(transaction=False)
        for tier in tiers:
            window_num = int(now // tier.window_seconds)
            pipe.get(f"test_hier:{tier.name}:{tier.identifier}:req:{window_num}")
            pipe.get(f"test_hier:{tier.name}:{tier.identifier}:tok:{window_num}")
        results = pipe.execute()

        blocked_by = None
        for i, tier in enumerate(tiers):
            current_req = int(results[i * 2] or 0)
            current_tok = int(results[i * 2 + 1] or 0)
            if current_req + 1 > tier.max_requests or current_tok + tokens > tier.max_tokens:
                blocked_by = tier.name
                break

        if not blocked_by:
            pipe = self.client.pipeline(transaction=True)
            for tier in tiers:
                window_num = int(now // tier.window_seconds)
                req_key = f"test_hier:{tier.name}:{tier.identifier}:req:{window_num}"
                tok_key = f"test_hier:{tier.name}:{tier.identifier}:tok:{window_num}"
                pipe.incr(req_key)
                pipe.expire(req_key, tier.window_seconds)
                pipe.incrby(tok_key, tokens)
                pipe.expire(tok_key, tier.window_seconds)
            pipe.execute()

        return {"allowed": blocked_by is None, "blocked_by": blocked_by}


# =============================================================================
# Test: Budget-Based Limiting
# =============================================================================


class TestBudget:
    """Test dollar-budget rate limiting."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Clean budget test keys."""
        self.client = client
        for key in client.scan_iter(match="test_budget:*"):
            client.delete(key)
        yield
        for key in client.scan_iter(match="test_budget:*"):
            client.delete(key)

    def test_allows_within_budget(self):
        """Request allowed when cost fits in budget."""
        window_num = int(time.time() // 3600)
        key = f"test_budget:user1:{window_num}"
        self.client.delete(key)

        current = float(self.client.get(key) or 0)
        cost = 0.03
        budget = 10.00
        assert current + cost <= budget

        self.client.incrbyfloat(key, cost)
        self.client.expire(key, 3600)
        assert float(self.client.get(key)) == pytest.approx(0.03)

    def test_blocks_over_budget(self):
        """Request blocked when cost would exceed budget."""
        window_num = int(time.time() // 3600)
        key = f"test_budget:user2:{window_num}"
        self.client.delete(key)

        # Pre-fill to near budget
        self.client.set(key, "9.98")
        self.client.expire(key, 3600)

        current = float(self.client.get(key) or 0)
        cost = 0.03
        budget = 10.00
        assert current + cost > budget  # Would exceed

    def test_incremental_spend(self):
        """Multiple small spends accumulate correctly."""
        window_num = int(time.time() // 3600)
        key = f"test_budget:user3:{window_num}"
        self.client.delete(key)

        for _ in range(10):
            self.client.incrbyfloat(key, 0.03)
        self.client.expire(key, 3600)

        total = float(self.client.get(key))
        assert total == pytest.approx(0.30, abs=0.001)


# =============================================================================
# Test: Concurrent Agent Slots
# =============================================================================


class TestConcurrentSlots:
    """Test Sorted Set-based concurrent agent limiting."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Clean concurrent test keys."""
        self.client = client
        self.client.delete("test_concurrent:user1")
        yield
        self.client.delete("test_concurrent:user1")

    def test_acquires_slot(self):
        """Can acquire a slot when under the limit."""
        key = "test_concurrent:user1"
        now = time.time()
        ttl = 300

        self.client.zremrangebyscore(key, "-inf", str(now))
        current = self.client.zcard(key)
        assert current < 3

        self.client.zadd(key, {"agent-1": now + ttl})
        assert self.client.zcard(key) == 1

    def test_blocks_at_max_concurrent(self):
        """Cannot acquire a slot when at the limit."""
        key = "test_concurrent:user1"
        now = time.time()
        ttl = 300

        # Fill 3 slots
        self.client.zadd(key, {
            "agent-1": now + ttl,
            "agent-2": now + ttl,
            "agent-3": now + ttl,
        })

        self.client.zremrangebyscore(key, "-inf", str(now))
        current = self.client.zcard(key)
        assert current >= 3  # At limit

    def test_expired_slots_cleaned(self):
        """Expired slots are cleaned up on next check."""
        key = "test_concurrent:user1"
        now = time.time()

        # Add 3 slots that have already expired
        self.client.zadd(key, {
            "agent-old-1": now - 100,
            "agent-old-2": now - 50,
            "agent-old-3": now - 10,
        })

        # Clean expired
        self.client.zremrangebyscore(key, "-inf", str(now))
        assert self.client.zcard(key) == 0  # All cleaned
