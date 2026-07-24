# Firecrawl + Valkey Cookbook

> Use Valkey as Firecrawl's cache backend for job queues, rate limiting, and crawl state management.
> Valkey is a drop-in replacement for Redis — same protocol, same client libraries, better performance.

## Cookbooks

| # | Cookbook | Level |
| --- | --- | --- |
| 01 | [Getting Started](01-getting-started.md) | Beginner |
| 02 | [Self-Hosting with Valkey](02-self-hosting.md) | Intermediate |
| 03 | [Production Operations](03-production-operations.md) | Intermediate |

## Prerequisites

- Docker and Docker Compose installed
- Firecrawl API key (for cloud usage) or a self-hosted setup
- Basic familiarity with web scraping concepts

## How Firecrawl Uses Valkey

Firecrawl relies on Valkey (or Redis) as its primary data backbone for coordinating distributed
scraping and crawling operations:

- **BullMQ Job Queues** — All crawl and scrape jobs are enqueued and processed through BullMQ,
  which uses Valkey lists and sorted sets for reliable job delivery and retry semantics.
- **Rate Limiting** — The `INCR` + `EXPIRE` pattern implements sliding-window rate limits per
  domain and per API key, preventing abuse and respecting robots.txt crawl-delay.
- **Crawl State (Sorted Sets)** — Sorted sets track the URL frontier with priority scores,
  allowing Firecrawl to process high-value pages first.
- **URL Deduplication (Sets)** — `SADD` checks prevent re-crawling the same URL within a
  crawl session, saving resources and avoiding infinite loops.
- **Distributed Locks (Redlock)** — Redlock-based locking coordinates concurrent workers to
  prevent duplicate processing of the same crawl job.
- **Caching (GET/SET with TTL)** — Scraped content is cached with configurable TTL to avoid
  redundant fetches for recently-seen pages.

## Quick Start

```bash
# Clone Firecrawl
git clone https://github.com/mendableai/firecrawl.git
cd firecrawl

# Switch Redis to Valkey in docker-compose.yaml
sed -i.bak 's|image: redis:alpine|image: valkey/valkey:alpine|' docker-compose.yaml && rm docker-compose.yaml.bak

# Configure environment
cp .env.example .env
# Edit .env with your settings (REDIS_URL stays the same)

# Start all services
docker compose up -d

# Verify Valkey is running
docker exec firecrawl-redis-1 valkey-cli INFO SERVER | grep server_name
# server_name:valkey
```

## References

- [Firecrawl Documentation](https://docs.firecrawl.dev/)
- [Firecrawl GitHub](https://github.com/mendableai/firecrawl)
- [PR #2901 — Valkey Test Coverage](https://github.com/firecrawl/firecrawl/pull/2901) (open)

> **Note:** This cookbook demonstrates community-tested compatibility between
> Firecrawl and Valkey. The upstream PR adds CI matrix testing but has not yet
> merged. The integration works because ioredis is wire-compatible with both backends.

- [Valkey Documentation](https://valkey.io/docs/)
- [BullMQ Documentation](https://docs.bullmq.io/)

---

[← Back to Valkey Samples](../../../README.md)
