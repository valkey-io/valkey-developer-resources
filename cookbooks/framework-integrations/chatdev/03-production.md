# Production Deployment with ChatDev + Valkey

> Configure TLS encryption, ACL auth, TTL policies, and multi-process deployments for production ChatDev workflows.

**Advanced** · Python · ~15 min

This cookbook covers hardening ValkeyMemory for production: encrypting connections, authenticating with ACL, managing memory growth, and running multiple workflow processes against a shared Valkey instance.

## TLS Encryption

Enable TLS to encrypt data in transit (required for any non-localhost deployment):

```yaml
memory:
  - name: production_memory
    type: valkey
    config:
      host: valkey.internal.company.com
      port: 6380
      use_tls: true
      password: ${VALKEY_PASSWORD}
      index_name: prod_memory
      embedding:
        provider: openai
        model: text-embedding-3-small
        api_key: ${API_KEY}
```

The `use_tls: true` flag passes `use_tls=True` to `GlideClientConfiguration`, which enables TLS negotiation on the connection.

For cloud-managed Valkey (e.g., Amazon ElastiCache, Google Memorystore), TLS is typically mandatory.

## ACL Authentication

Valkey supports username/password authentication via Access Control Lists:

```yaml
memory:
  - name: production_memory
    type: valkey
    config:
      host: valkey.internal.company.com
      port: 6380
      username: chatdev_app
      password: ${VALKEY_PASSWORD}
      use_tls: true
      index_name: prod_memory
      embedding:
        provider: openai
        model: text-embedding-3-small
        api_key: ${API_KEY}
```

Set up the ACL on the Valkey server:

```bash
# Run from bash (not inside valkey-cli). Replace 'yourpassword' with the actual password.
valkey-cli ACL SETUSER chatdev_app on ">yourpassword" "~memory:*" +HSET +HGETALL +EXPIRE +DEL +FT.CREATE +FT.SEARCH +FT.INFO
```

This restricts the application to only the commands and key patterns it needs.

## TTL Policies for Memory Management

Without TTL, memories accumulate indefinitely. Choose a strategy based on your use case:

### Session-scoped memory (recommended for most deployments)

```yaml
config:
  ttl_seconds: 86400    # 24 hours
```

### Tiered memory with multiple stores

```yaml
memory:
  # Short-term: recent conversation context
  - name: short_term
    type: valkey
    config:
      host: valkey.internal.company.com
      port: 6380
      index_name: short_term_idx
      key_prefix: "st:"
      ttl_seconds: 3600       # 1 hour
      embedding:
        provider: openai
        model: text-embedding-3-small
        api_key: ${API_KEY}

  # Long-term: important facts (no expiry)
  - name: long_term
    type: valkey
    config:
      host: valkey.internal.company.com
      port: 6380
      index_name: long_term_idx
      key_prefix: "lt:"
      embedding:
        provider: openai
        model: text-embedding-3-small
        api_key: ${API_KEY}
```

Attach both to an agent with different top_k:

```yaml
memories:
  - name: short_term
    top_k: 5
    read: true
    write: true
  - name: long_term
    top_k: 2
    read: true
    write: false   # Only written by a separate curation process
```

## Multi-Process Deployment

ValkeyMemory is safe for multi-process use. Multiple ChatDev worker processes can read and write to the same index concurrently:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Worker Process 1│     │ Worker Process 2│     │ Worker Process 3│
│  ValkeyMemory   │     │  ValkeyMemory   │     │  ValkeyMemory   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │     Valkey Server       │
                    │   (Search module)       │
                    │   index: prod_memory    │
                    └─────────────────────────┘
```

Each process creates its own `GlideClient` connection. The FT index creation is idempotent — if the index already exists, ValkeyMemory silently skips creation.

Key properties:
- **Writes are atomic**: `HSET` is a single atomic command
- **Reads are eventually consistent**: newly written memories appear in search results after the index updates (typically < 1ms)
- **No coordination needed**: no distributed locks or leader election

## Monitoring

Track memory usage and search performance:

> These commands assume `valkey-cli` is installed locally and can reach the Valkey server directly (production deployments). For Docker-based dev setups, prefix with `docker exec valkey`.

```bash
# Document count
valkey-cli FT.INFO prod_memory | grep num_docs

# Memory usage
valkey-cli FT.INFO prod_memory | grep space_usage

# Index status
valkey-cli FT.INFO prod_memory | grep indexing
```

Set alerts on:
- `num_docs` growing beyond expected bounds (indicates TTL not working)
- `space_usage` approaching memory limits
- `indexing` = 1 for extended periods (index is still building)

## Configuration Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | str | `localhost` | Valkey server address |
| `port` | int | `6379` | Server port (1-65535) |
| `username` | str | None | ACL username |
| `password` | str | None | Authentication password |
| `db` | int | `0` | Database index (0-15) |
| `use_tls` | bool | `false` | Enable TLS encryption |
| `index_name` | str | `memory_index` | FT index name |
| `key_prefix` | str | `memory:` | Hash key prefix |
| `ttl_seconds` | int | None | Per-entry TTL (null = no expiry) |
| `embedding` | object | — | EmbeddingConfig (provider, model, api_key) |

> **Note:** GLIDE defaults to a 250ms request timeout, which assumes local-network latency. For remote deployments (cross-region, cloud-managed), increase this via `GlideClientConfiguration` in the ChatDev source if needed.

## When to Use ValkeyMemory vs Alternatives

| Scenario | Recommended Backend |
|----------|-------------------|
| Local dev, single process, no server | SimpleMemory (FAISS) |
| Cloud-managed, zero infrastructure | Mem0Memory |
| Self-hosted, multi-process, need persistence | **ValkeyMemory** |
| Privacy-sensitive, data must stay on-prem | **ValkeyMemory** |
