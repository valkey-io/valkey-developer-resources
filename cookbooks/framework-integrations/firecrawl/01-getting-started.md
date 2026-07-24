# Getting Started with Firecrawl and Valkey

> Run Firecrawl with Valkey as the cache backend — same functionality as Redis with zero code changes.

**Beginner** · Docker · ~10 min

**Who is this for:** Developers who want to try Firecrawl with Valkey locally, either for evaluation or to replace Redis in an existing Firecrawl setup.

## Prerequisites

- Docker and Docker Compose installed
- Git installed

> **Security Note:** This guide uses default Valkey settings suitable for local development.
> For production deployments, review the [Valkey security documentation](https://valkey.io/topics/security/)
> to configure authentication, network binding, and TLS.

## Step 1: Clone Firecrawl

```bash
git clone https://github.com/mendableai/firecrawl.git
cd firecrawl
```

## Step 2: Switch to Valkey

Edit `docker-compose.yaml` and change the Redis image to Valkey:

```yaml
# Before
redis:
  image: redis:alpine
  ports:
    - "6379:6379"

# After
redis:
  image: valkey/valkey:alpine
  ports:
    - "6379:6379"
```

The service name stays `redis` so that existing `REDIS_URL` references continue to resolve
via Docker DNS without any additional changes.

## Step 3: Configure Environment

```bash
cp .env.example .env
```

Open `.env` and verify the Redis URL points to the container:

```bash
REDIS_URL=redis://redis:6379
```

No changes needed — Valkey speaks the same protocol, so the `redis://` scheme works as-is.

## Step 4: Start Services

```bash
docker compose up -d
```

This starts Valkey, the Firecrawl API server, and worker processes.

## Step 5: Verify Valkey is Running

```bash
docker exec firecrawl-redis-1 valkey-cli INFO SERVER
```

Look for the `server_name` field in the output:

```text
# Server
server_name:valkey
valkey_version:8.1.1
```

If you see `server_name:valkey`, the swap was successful.

You can also check connectivity from the Firecrawl containers:

```bash
docker exec firecrawl-redis-1 valkey-cli PING
# PONG
```

## Step 6: Test a Scrape

```bash
curl -X POST http://localhost:3002/v1/scrape \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-YOUR_API_KEY" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown"]
  }'
```

A successful response returns the scraped content in markdown format:

```json
{
  "success": true,
  "data": {
    "markdown": "# Example Domain\n\nThis domain is for use in illustrative examples...",
    "metadata": {
      "title": "Example Domain",
      "statusCode": 200
    }
  }
}
```

## How Backend Detection Works

Firecrawl detects whether it's connected to Redis or Valkey using the `INFO SERVER` command.
The response includes a `server_name` field:

- `server_name:redis` → Redis
- `server_name:valkey` → Valkey

This detection is informational — Firecrawl uses the same code paths regardless of backend.
The ioredis client library works identically with both servers since Valkey maintains full
protocol compatibility.

## Troubleshooting

### Connection refused errors

```text
Error: connect ECONNREFUSED 127.0.0.1:6379
```

Ensure the Valkey container is running:

```bash
docker compose ps
docker compose logs redis
```

### Container name mismatch

If `docker exec firecrawl-redis-1` fails, check the actual container name:

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

### Firecrawl can't connect to Valkey

Verify the containers are on the same Docker network:

```bash
docker network inspect firecrawl_default
```

The `REDIS_URL` must use the Docker service name (`redis`) not `localhost` when running
inside Docker Compose.

### API key not set

If scrape requests return 401, ensure you've set a valid API key in `.env` or use the
test key for local development as documented in Firecrawl's README.

---

**Next:** [Self-Hosting with Valkey →](02-self-hosting.md)

[← Back to Firecrawl Cookbook](README.md)
