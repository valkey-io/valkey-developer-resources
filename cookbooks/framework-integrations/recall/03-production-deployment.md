# Production Deployment of Recall with Valkey

> Deploy Recall with Valkey for team use — TLS encryption, authentication,
> Docker Compose orchestration, and operational monitoring.

**Intermediate** · TypeScript/Node.js · ~20 min

**Who is this for:** DevOps engineers and team leads deploying Recall as shared
AI memory infrastructure for multiple developers or CI/CD pipelines.
You should have completed the [Workspace Memory](02-workspace-memory.md) guide.

## Prerequisites

- Docker and Docker Compose
- A TLS certificate (or willingness to use self-signed for internal use)
- Understanding of network security basics

> **Security note:** Recall stores potentially sensitive conversation context.
> Production deployments must use authentication and TLS. Never expose Valkey
> ports to the public internet. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Architecture Overview

```text
┌─────────────────────┐
│ Developer Machines  │
│ (Claude Desktop/    │
│  Claude Code)       │
└────────┬────────────┘
         │ MCP (stdio, local)
         ▼
┌─────────────────────┐
│ Recall MCP Server   │
│ (runs per-user)     │
└────────┬────────────┘
         │ TLS + AUTH (TCP 6380)
         ▼
┌─────────────────────┐
│ Valkey              │
│ (shared instance)   │
│ Persistence: AOF    │
└─────────────────────┘
```

Each developer runs Recall locally (it's an MCP stdio server), but all connect
to a shared Valkey instance for team knowledge sharing.

## Docker Compose Setup

```yaml
# docker-compose.yml
services:
  valkey:
    image: valkey/valkey:8.1.1
    ports:
      - "6380:6379"
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/usr/local/etc/valkey/valkey.conf
      - ./certs:/tls
    command: valkey-server /usr/local/etc/valkey/valkey.conf
    healthcheck:
      test: ["CMD", "valkey-cli", "--tls", "--cert", "/tls/valkey.crt",
             "--key", "/tls/valkey.key", "--cacert", "/tls/ca.crt",
             "-a", "$$VALKEY_PASSWORD", "PING"]
      interval: 10s
      timeout: 5s
      retries: 5
    environment:
      - VALKEY_PASSWORD=${VALKEY_PASSWORD:-change-me-in-production}
    restart: unless-stopped

volumes:
  valkey-data:
```

## Valkey Configuration

Create `valkey.conf` for production hardening:

```conf
# valkey.conf — Production configuration for Recall

# Authentication
requirepass change-me-in-production

# TLS
tls-port 6379
port 0
tls-cert-file /tls/valkey.crt
tls-key-file /tls/valkey.key
tls-ca-cert-file /tls/ca.crt
tls-auth-clients optional

# Persistence (AOF for durability)
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Memory management
maxmemory 256mb
maxmemory-policy noeviction

# Security hardening
# NOTE: rename-command is deprecated in Valkey 8.x — prefer ACL rules (see below).
# Shown here for environments where ACL support is limited.
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG "RECALL_CONFIG"
rename-command DEBUG ""

# Network
bind 0.0.0.0
tcp-keepalive 300
timeout 300

# Logging
loglevel notice
```

### Key Configuration Choices

| Setting | Rationale |
| ------- | --------- |
| `maxmemory-policy noeviction` | Memories are precious — never evict silently |
| `appendonly yes` | Durability over speed (memories must survive restart) |
| `rename-command FLUSHALL ""` | Prevent accidental data loss |
| `tls-port 6379` + `port 0` | TLS-only connections, no plaintext |

## TLS Certificate Setup

### Self-Signed (Internal/Development)

```bash
mkdir -p certs

# Generate CA
openssl genrsa -out certs/ca.key 4096
openssl req -x509 -new -nodes -key certs/ca.key \
  -sha256 -days 3650 -out certs/ca.crt \
  -subj "/CN=Recall Valkey CA"

# Generate server cert
openssl genrsa -out certs/valkey.key 2048
openssl req -new -key certs/valkey.key \
  -out certs/valkey.csr \
  -subj "/CN=valkey"
openssl x509 -req -in certs/valkey.csr \
  -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
  -out certs/valkey.crt -days 365 -sha256

# Clean up
rm certs/valkey.csr certs/ca.srl
```

### Connecting Recall with TLS

Recall's Valkey backend uses `@valkey/valkey-glide`, which supports TLS.
Currently, you configure TLS via the `REDIS_URL` fallback with a `rediss://` scheme:

```json
{
  "mcpServers": {
    "recall": {
      "command": "npx",
      "args": ["-y", "@joseairosa/recall"],
      "env": {
        "REDIS_URL": "rediss://default:your-password@valkey-host:6380",
        "ANTHROPIC_API_KEY": "your-anthropic-api-key"
      }
    }
  }
}
```

> **Note:** As of Recall v1.15, the Valkey-specific `BACKEND_TYPE=valkey` path
> does not support TLS configuration directly. Use `REDIS_URL` with `rediss://`
> scheme for TLS connections, which routes through the Redis adapter but connects
> to Valkey the same way.

## Access Control with Valkey ACLs

For multi-team deployments, create per-team users:

```bash
docker exec -it valkey-recall valkey-cli --tls \
  --cert /tls/valkey.crt --key /tls/valkey.key --cacert /tls/ca.crt \
  -a your-admin-password

# Create a user for team-alpha
ACL SETUSER team-alpha on >team-alpha-password ~recall:ws:* ~recall:global:* +@all -@admin

# Create a read-only user for monitoring
ACL SETUSER monitor on >monitor-password ~recall:* +info +keys +scan +hgetall +zrange -@write
```

## Monitoring

### Memory Usage Tracking

```bash
#!/bin/bash
# scripts/check_recall_health.sh

VALKEY_HOST="${VALKEY_HOST:-localhost}"
VALKEY_PORT="${VALKEY_PORT:-6380}"
VALKEY_PASS="${VALKEY_PASSWORD:-change-me-in-production}"

# Total memory keys
total_memories=$(docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" \
  KEYS "recall:*:memory:*" 2>/dev/null | wc -l)

# Memory usage
memory_used=$(docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" \
  INFO memory 2>/dev/null | grep "used_memory_human")

# Workspace count
workspaces=$(docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" \
  KEYS "recall:ws:*:index" 2>/dev/null | wc -l)

echo "Recall Health Check"
echo "==================="
echo "Total memories: $total_memories"
echo "Workspaces: $workspaces"
echo "Memory: $memory_used"
```

### Key Metrics to Monitor

| Metric | Command | Alert Threshold |
| ------ | ------- | --------------- |
| Total memories | `KEYS "recall:*:memory:*" \| wc -l` | >10,000 (review retention) |
| Memory usage | `INFO memory` → `used_memory` | >200MB (approaching limit) |
| Connected clients | `INFO clients` → `connected_clients` | >50 (connection leak) |
| Persistence lag | `INFO persistence` → `aof_last_write_status` | Not "ok" |

### Prometheus Integration

If you run Prometheus, add the Valkey exporter:

```yaml
# Add to docker-compose.yml
  valkey-exporter:
    image: oliver006/redis_exporter:v1.58.0
    ports:
      - "9121:9121"
    environment:
      - REDIS_ADDR=rediss://valkey:6379
      - REDIS_PASSWORD=${VALKEY_PASSWORD}
    depends_on:
      valkey:
        condition: service_healthy
```

## Data Retention

Recall accumulates memories over time. For teams, implement retention policies:

```bash
# Find memories older than 90 days (check timestamps in hash fields)
docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" \
  --scan --pattern "recall:*:memory:*" | while read key; do
    created=$(docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" \
      HGET "$key" created_at)
    # Compare with threshold and delete if stale
  done
```

Or use Recall's built-in consolidation — ask Claude:

```text
Find duplicate memories and consolidate them
```

This uses the `find_duplicates` and `consolidate_memories` tools to merge
similar entries automatically.

## Backup Strategy

### Automated Daily Backups

```bash
#!/bin/bash
# scripts/backup_recall.sh

BACKUP_DIR="/backups/recall"
DATE=$(date +%Y%m%d)

mkdir -p "$BACKUP_DIR"

# Trigger RDB snapshot
docker exec valkey-recall valkey-cli -a "$VALKEY_PASS" BGSAVE
sleep 5

# Copy snapshot
docker cp valkey-recall:/data/dump.rdb "$BACKUP_DIR/recall-$DATE.rdb"

# Keep last 30 days
find "$BACKUP_DIR" -name "*.rdb" -mtime +30 -delete

echo "Backup complete: $BACKUP_DIR/recall-$DATE.rdb"
```

### Disaster Recovery

```bash
# Stop Valkey
docker compose down

# Replace data file
cp /backups/recall/recall-20260723.rdb ./data/dump.rdb

# Restart
docker compose up -d
```

## Team Onboarding

For each new team member:

1. Share the Valkey connection details (host, port, password) securely
2. Have them add the MCP config to their Claude Desktop/Code settings:

    ```json
    {
      "mcpServers": {
        "recall": {
          "command": "npx",
          "args": ["-y", "@joseairosa/recall"],
          "env": {
            "REDIS_URL": "rediss://team-alpha:team-password@valkey.internal:6380",
            "WORKSPACE_MODE": "hybrid",
            "ANTHROPIC_API_KEY": "their-own-api-key"
          }
        }
      }
    }
    ```

3. Restart Claude — they immediately have access to team global memories

## Troubleshooting

### TLS handshake failures

Verify the certificate chain:

```bash
openssl s_client -connect valkey-host:6380 -CAfile certs/ca.crt
```

### "NOAUTH Authentication required"

The password in `REDIS_URL` must be URL-encoded if it contains special characters:

```bash
# If password is "p@ss:word" → encode as "p%40ss%3Aword"
REDIS_URL="rediss://default:p%40ss%3Aword@valkey-host:6380"
```

### Memory keeps growing

Recall doesn't auto-expire memories. Use consolidation:

```text
Find and merge duplicate memories, then delete any with importance below 3
```

Or set a hard limit in `valkey.conf` with `maxmemory` — with `noeviction` policy,
Recall will receive write errors and surface them to Claude rather than silently
losing data.

---

[← Back to Recall Cookbook](README.md)
