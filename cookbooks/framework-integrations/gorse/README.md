# Gorse + Valkey Cache Backend Cookbook

> Use Valkey as a cache storage backend for [Gorse](https://gorse.io/), an open-source recommendation engine, replacing Redis TimeSeries with a sorted-set + hash implementation.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure Gorse to use Valkey as its cache store with sorted-set time series | Beginner, ~15 min, Go |

## Prerequisites

- **Valkey 8.1+** with the `valkey-search` module (use `valkey/valkey-bundle` image)
- **Docker** and **Docker Compose**
- **Go 1.23+** (for running the sample)

## How Gorse Uses Valkey

Gorse is an open-source recommendation system written in Go. It uses a cache store for intermediate computation results, item scores, and time series metrics. The Valkey integration (introduced in [gorse-io/gorse#1263](https://github.com/gorse-io/gorse/pull/1263)) reuses the existing `go-redis` client — zero new dependencies — since Valkey is wire-compatible with Redis for all commands except the TimeSeries module.

Key patterns demonstrated:

- **Embedding pattern** — `RedisValkey` embeds the existing `Redis` struct, inheriting all KV, queue, scores, search, scan, and purge operations unchanged.
- **Sorted-set time series** — Replaces `TS.ADD`/`TS.RANGE` with `ZADD` (timestamp index) + `HSET` (values), with client-side LAST-bucket aggregation.
- **Auto-detection** — The factory function detects Valkey via `INFO server` (`server_name:valkey`) and automatically selects the correct implementation.
- **FT.SEARCH compatibility** — Valkey Search module commands (`FT.CREATE`, `FT.SEARCH`, `FT.DROPINDEX`, `FT._LIST`) work identically via the same go-redis client.

## Why go-redis (Not valkey-go or valkey-glide)

| Option | Issue |
|--------|-------|
| `valkey-glide` | Requires CGo (Rust FFI). Gorse builds with `CGO_ENABLED=0` for static `FROM scratch` binaries. |
| `valkey-go` | Pure Go but adds a new dependency for wire-compatible commands. Unnecessary when go-redis already works. |
| `go-redis` (this approach) | Zero new deps. Valkey is wire-compatible. Only time series needs a different implementation. |

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "strconv"
    "time"

    "github.com/redis/go-redis/v9"
)

func main() {
    client := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    ctx := context.Background()

    // Store a time series point using sorted set + hash
    name := "click_through_rate"
    ts := time.Now()
    tsMsStr := strconv.FormatInt(ts.UnixMilli(), 10)

    // ZADD for timestamp index, HSET for value storage
    pipe := client.Pipeline()
    pipe.ZAdd(ctx, "ts_index:"+name, redis.Z{Score: float64(ts.UnixMilli()), Member: tsMsStr})
    pipe.HSet(ctx, "ts_data:"+name, tsMsStr, "0.42")
    _, err := pipe.Exec(ctx)
    if err != nil {
        panic(err)
    }
    fmt.Println("Stored time series point successfully")
}
```

---

[← Back to Valkey Samples](../../../README.md)
