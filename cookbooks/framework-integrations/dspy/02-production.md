# Production Deployment

> Harden DSPy's ValkeyCache for production: TTL policies, TLS encryption, authentication, cluster mode, tenant isolation, and restricted deserialization.

**Intermediate** · Python · ~20 min

**Who is this for:** Teams deploying DSPy programs to production where cache data crosses a network, multiple tenants share infrastructure, or compliance requires encryption in transit.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- A Valkey instance accessible from your deployment environment
- TLS certificates (for the encryption section)

> **Security note:** Production Valkey instances must use authentication and TLS.
> The patterns below show how to configure both.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for full hardening guidance.

## TTL: Automatic Cache Expiry

By default, cached responses persist indefinitely. For production, set a TTL to bound storage growth and ensure stale responses age out:

```python
from dspy.clients import ValkeyCache

# Entries expire after 1 hour
dspy.cache = ValkeyCache(
    host="valkey.internal",
    port=6379,
    ttl_seconds=3600,
)
```

Choose TTL based on your workload:

| Use Case | Suggested TTL | Rationale |
|----------|---------------|-----------|
| Development iteration | `None` (no expiry) | Avoid re-running expensive LLM calls |
| Production API serving | `3600` (1 hour) | Bound memory, allow model updates |
| Optimization sweeps | `86400` (24 hours) | Long enough for full sweep, expires after |
| Ephemeral batch jobs | `1800` (30 min) | Clean up after job completes |

Verify TTL is set with `valkey-cli`:

```bash
valkey-cli TTL "dspy:cache:<key_prefix_here>"
# Returns remaining seconds, or -1 if no expiry
```

## Authentication

### Password-Only (Valkey 6 Default)

```python
dspy.cache = ValkeyCache(
    host="valkey.internal",
    port=6379,
    password="your-valkey-password",
    tls=True,
)
```

### ACL Authentication (Valkey 6+)

For multi-user environments, use ACL usernames with scoped permissions:

```python
dspy.cache = ValkeyCache(
    host="valkey.internal",
    port=6379,
    username="dspy-app",
    password="per-user-password",
    tls=True,
)
```

Minimal ACL for ValkeyCache (only needs string + key operations):

```text
ACL SETUSER dspy-app on >password ~dspy:cache:* +get +set +exists +del +ping
```

## TLS Encryption

ValkeyCache warns at startup when connecting to a remote host without TLS:

```text
WARNING: ValkeyCache connecting to remote host valkey.internal without TLS.
Prompts, completions, and the AUTH password will be sent in plaintext.
```

### Basic TLS

```python
dspy.cache = ValkeyCache(
    host="valkey.internal",
    port=6380,
    tls=True,
    password="secret",
)
```

### Custom CA Certificate

For private PKI (typical in AWS ElastiCache, GCP Memorystore, Azure Cache):

```python
from glide import TlsAdvancedConfiguration

tls_config = TlsAdvancedConfiguration(
    root_pem_cacerts="/path/to/custom-ca.pem",
)

dspy.cache = ValkeyCache(
    host="valkey.internal",
    port=6380,
    tls_config=tls_config,
    password="secret",
)
```

## Cluster Mode

For high-availability deployments, Valkey Cluster distributes keys across multiple nodes with automatic failover:

```python
dspy.cache = ValkeyCache(
    host="cluster-node-1.internal",
    port=6379,
    cluster=True,
    tls=True,
    password="cluster-password",
)
```

valkey-glide handles topology discovery, slot routing, and failover transparently — no application code changes required.

## Multi-Tenant Isolation

On shared Valkey instances, use distinct `key_prefix` values to isolate tenants:

```python
# Tenant A's cache
dspy.cache = ValkeyCache(
    host="shared-valkey.internal",
    key_prefix="tenant-a:dspy:",
)

# Tenant B's cache (same server, different namespace)
dspy.cache = ValkeyCache(
    host="shared-valkey.internal",
    key_prefix="tenant-b:dspy:",
)
```

Combine with ACL rules for enforcement:

```text
ACL SETUSER tenant-a on >pass-a ~tenant-a:dspy:* +get +set +exists +del +ping
ACL SETUSER tenant-b on >pass-b ~tenant-b:dspy:* +get +set +exists +del +ping
```

## Restricted Pickle Deserialization

ValkeyCache defaults to `restrict_pickle=True`, which only allows `litellm.types.*` and `openai.types.*` to be deserialized.
This prevents arbitrary code execution from poisoned cache entries on shared infrastructure.

If you cache custom response types, register them explicitly:

```python
from myapp.models import CustomResponse

dspy.cache = ValkeyCache(
    host="valkey.internal",
    restrict_pickle=True,
    safe_types=[CustomResponse],
)
```

A rejected entry is evicted automatically and logged:

```text
WARNING: Rejected non-allowlisted cached value for key a1b2c3...; evicting
```

## Context Manager for Cleanup

In batch jobs or Lambda functions, use the context manager to guarantee cleanup:

```python
with ValkeyCache(host="valkey.internal", ttl_seconds=1800) as cache:
    dspy.cache = cache
    # Run optimization sweep...
# Connection closed, background thread stopped
```

## Deployment Checklist

- [ ] TLS enabled (`tls=True` or `tls_config=...`)
- [ ] Authentication configured (`password=...`)
- [ ] TTL set appropriate to workload
- [ ] `key_prefix` unique per tenant/application
- [ ] `restrict_pickle=True` (default — don't disable on shared infra)
- [ ] ACL scoped to minimal required commands
- [ ] Valkey persistence configured (RDB/AOF) if cache durability matters

## Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `"localhost"` | Valkey server hostname |
| `port` | `6379` | Valkey server port |
| `ttl_seconds` | `None` | Cache entry TTL in seconds |
| `tls` | `False` | Enable TLS encryption |
| `tls_config` | `None` | Advanced TLS (custom CA, mTLS) |
| `request_timeout` | `500` | Per-command timeout in milliseconds |
| `password` | `None` | AUTH password |
| `username` | `None` | ACL username |
| `cluster` | `False` | Enable cluster mode |
| `key_prefix` | `"dspy:cache:"` | Namespace prefix for keys |
| `restrict_pickle` | `True` | Restrict deserialization to safe types |
| `safe_types` | `None` | Additional types to allow |

---

[← Getting Started](./01-getting-started.md) · [← Back to README](./README.md)
