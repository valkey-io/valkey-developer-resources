# Helicone + Valkey Integration Cookbook

> Helicone's Jawn API server uses Valkey for caching, rate limiting, and encrypted key storage
> through 5 distinct subsystems — all via core commands with zero modules required.

## Cookbooks

| Cookbook | Level | Description |
| ------- | ----- | ----------- |
| [Getting Started](01-getting-started.md) | Beginner | Set up Valkey locally and run Helicone's KV cache and rate-limiting patterns |
| [Production](02-production.md) | Intermediate | TLS, Lua scripting, monitoring, and encrypted storage |

## Prerequisites

- **Valkey** 8+
- **Docker** and **Docker Compose** for local development
- **Node.js** 20+ with npm
- **ioredis** 5+ (installed automatically with the sample)

## How Helicone Uses Valkey

Helicone connects to Valkey through a single client using only 8 core commands.
No Valkey modules are required. The integration uses only core string and scripting commands.

> **Note:** Helicone's production deployment hardcodes TLS (`tls: {}` in client options).
> The connection always requires a TLS-enabled Valkey endpoint — there is no env var to disable it.
> See [Production](02-production.md) for TLS configuration details.

| Subsystem | Commands | Description |
| --------- | -------- | ----------- |
| KV Cache | `GET`, `SET PX` | Generic L2 caching with millisecond TTL |
| Proxy Rate Limiter | `GET`, `SET EX` | Sliding-window rate limiting with second TTL |
| HTTP API Rate Limiter | `SCRIPT LOAD`, `EVALSHA`, `INCR`, `PTTL`, `PEXPIRE` | Atomic per-org request counting via Lua scripts |
| Usage Limit Cache | `GET`, `SET EX` | Caches ClickHouse usage query results for 1 hour |
| Encrypted Key/Auth Cache | `GET`, `SET EX` | AES-GCM encrypted provider keys and auth tokens |

## Quick Start

```javascript
import Redis from "ioredis";

const client = new Redis({ host: "localhost", port: 6379 });

// KV Cache: store with millisecond TTL (5 seconds)
await client.set("cache:greeting", JSON.stringify({ message: "Hello" }), "PX", 5000);

const result = await client.get("cache:greeting");
console.log(JSON.parse(result)); // { message: "Hello" }
```

## Running the Sample Tests

```bash
cd cookbooks/framework-integrations/helicone/sample
docker compose up -d
npm install
npm test
docker compose down
```

The test suite connects to Valkey on `localhost:6379` and verifies all 5 subsystem patterns.
When `VALKEY_HOST` is not set, tests exit with code 0 and a "skipped" message.

## References

- [Helicone Documentation](https://docs.helicone.ai/)
- [Helicone GitHub](https://github.com/Helicone/helicone)
- [Valkey Documentation](https://valkey.io/docs/)
- [ioredis Documentation](https://github.com/redis/ioredis)

---

[← Back to Valkey Samples](../../../README.md)
