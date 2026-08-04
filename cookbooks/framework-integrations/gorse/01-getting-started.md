# Getting Started with Gorse and Valkey

> Connect the Gorse recommendation engine to Valkey as its cache backend, using sorted-set time series to replace Redis TimeSeries.

**Beginner** · Go · ~15 min

**Who is this for:** Go developers running Gorse who want to use Valkey instead of Redis for the cache layer, or anyone implementing time series storage on Valkey without the TimeSeries module.

## Prerequisites

- Docker installed
- Go 1.23+ installed
- Basic familiarity with Valkey/Redis commands

## Step 1: Start Valkey with the Search Module

Gorse's cache layer requires the `valkey-search` module for score-based document indexing (`FT.CREATE`, `FT.SEARCH`). Use the `valkey-bundle` image:

```bash
docker run -d --name valkey \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Understand the Architecture

Gorse's Valkey integration uses an embedding pattern — `RedisValkey` embeds the existing `Redis` struct and overrides only what's different:

| Component | Role |
|-----------|------|
| `go-redis` client | Wire-compatible connection to Valkey (rewriting `valkey://` → `redis://` for URL parsing) |
| `Redis` struct | Handles KV, queue, scores, search (FT.*), scan, and purge — all wire-compatible |
| `RedisValkey` struct | Embeds `Redis`, overrides only `AddTimeSeriesPoints` and `GetTimeSeriesPoints` |
| Sorted set (`ZADD`) | Timestamp index — score = unix_ms, member = unix_ms string |
| Hash (`HSET`) | Value storage — field = unix_ms string, value = float64 string |

This keeps **zero new dependencies** compared to the existing Redis implementation.

## Step 3: Detect Valkey vs Redis

The factory function auto-detects whether the server is Valkey by checking `INFO server`:

```go
func isValkey(client redis.UniversalClient) bool {
    info, err := client.Info(context.Background(), "server").Result()
    if err != nil {
        return false
    }
    for _, line := range strings.Split(info, "\n") {
        if strings.TrimSpace(line) == "server_name:valkey" {
            return true
        }
    }
    return false
}
```

This means applications can connect with either `redis://` or `valkey://` URLs and get the correct implementation automatically.

## Step 4: Store Time Series Points

Redis uses the TimeSeries module (`TS.ADD`, `TS.RANGE`) which Valkey doesn't have. The replacement uses two keys per series:

```go
func AddTimeSeriesPoints(ctx context.Context, client redis.Cmdable, points []TimeSeriesPoint) error {
    if len(points) == 0 {
        return nil
    }
    pipe := client.Pipeline()
    for _, point := range points {
        tsMsStr := strconv.FormatInt(point.Timestamp.UnixMilli(), 10)
        indexKey := "ts_index:" + point.Name
        dataKey := "ts_data:" + point.Name

        // ZADD: score=timestamp_ms, member=timestamp_ms (handles duplicates via score update)
        pipe.ZAdd(ctx, indexKey, redis.Z{
            Score:  float64(point.Timestamp.UnixMilli()),
            Member: tsMsStr,
        })
        // HSET: field=timestamp_ms, value=float64 (last-write-wins for duplicate timestamps)
        pipe.HSet(ctx, dataKey, tsMsStr, strconv.FormatFloat(point.Value, 'g', -1, 64))
    }
    _, err := pipe.Exec(ctx)
    return err
}
```

**Why this design:**

- `ZADD` naturally handles duplicate timestamps — updating the score is a no-op since score == member, and the member already exists. This matches Redis TimeSeries `DUPLICATE_POLICY LAST`.
- `HSET` naturally overwrites — writing the same field replaces the value (last-write-wins).
- Pipelining batches all writes into a single round-trip.

## Step 5: Query Time Series with Bucket Aggregation

Gorse queries time series with bucket aggregation (e.g., "give me the last value per 5-minute bucket"). This mirrors `TS.RANGE ... AGGREGATION last <bucket_ms>`:

```go
func GetTimeSeriesPoints(ctx context.Context, client *redis.Client, name string,
    begin, end time.Time, bucketDuration time.Duration) ([]TimeSeriesPoint, error) {

    indexKey := "ts_index:" + name
    dataKey := "ts_data:" + name

    // Fetch all timestamps in range from the sorted set
    members, err := client.ZRangeByScore(ctx, indexKey, &redis.ZRangeBy{
        Min: strconv.FormatInt(begin.UnixMilli(), 10),
        Max: strconv.FormatInt(end.UnixMilli(), 10),
    }).Result()
    if err != nil {
        return nil, err
    }
    if len(members) == 0 {
        return []TimeSeriesPoint{}, nil
    }

    // Fetch corresponding values from hash
    vals, err := client.HMGet(ctx, dataKey, members...).Result()
    if err != nil {
        return nil, err
    }

    // Client-side bucket aggregation: last value per bucket
    durationMs := bucketDuration.Milliseconds()
    type bucketEntry struct {
        timestamp int64
        value     float64
    }
    buckets := make(map[int64]*bucketEntry)

    for i, member := range members {
        if vals[i] == nil {
            continue
        }
        ts, _ := strconv.ParseInt(member, 10, 64)
        val, _ := strconv.ParseFloat(vals[i].(string), 64)
        bucketKey := (ts / durationMs) * durationMs
        if existing, ok := buckets[bucketKey]; !ok || ts > existing.timestamp {
            buckets[bucketKey] = &bucketEntry{timestamp: ts, value: val}
        }
    }

    // Sort and return
    sortedKeys := make([]int64, 0, len(buckets))
    for k := range buckets {
        sortedKeys = append(sortedKeys, k)
    }
    slices.Sort(sortedKeys)

    points := make([]TimeSeriesPoint, 0, len(sortedKeys))
    for _, bk := range sortedKeys {
        entry := buckets[bk]
        points = append(points, TimeSeriesPoint{
            Name:      name,
            Value:     entry.value,
            Timestamp: time.UnixMilli(bk).UTC(),
        })
    }
    return points, nil
}
```

**Trade-off:** This fetches all timestamps in the range into memory for client-side aggregation.
For Gorse's use case (metrics with bounded density — hourly/daily points over weeks), this is fine.
For extremely high-density data, consider adding `Count`/`Offset` pagination to `ZRangeByScore`.

## Step 6: Verify the Integration

Run the sample to confirm everything works:

```bash
cd sample/
docker compose up -d
go run .
```

Expected output:

```text
Connected to Valkey (server_name:valkey detected)
Stored 10 time series points
Queried 5-second buckets: 2 results
  bucket 2023-01-01 00:00:00 +0000 UTC → value: 5.000000
  bucket 2023-01-01 00:00:05 +0000 UTC → value: 10.000000
✅ Gorse-style Valkey cache patterns demonstrated successfully
```

## How It Works

| Valkey Command | Purpose | Redis TimeSeries Equivalent |
|----------------|---------|----------------------------|
| `ZADD ts_index:{name} {ms} {ms}` | Index timestamp | `TS.ADD {name} {ms} {val}` (timestamp part) |
| `HSET ts_data:{name} {ms} {val}` | Store value | `TS.ADD {name} {ms} {val}` (value part) |
| `ZRANGEBYSCORE ts_index:{name} {begin} {end}` | Range query timestamps | `TS.RANGE {name} {begin} {end}` (timestamp selection) |
| `HMGET ts_data:{name} {ms1} {ms2} ...` | Fetch values | `TS.RANGE` (value retrieval) |
| Client-side bucket aggregation | LAST per bucket | `TS.RANGE ... AGGREGATION last {bucket_ms}` |

## Configuration Reference

Gorse accepts Valkey via these URL schemes in `config.toml`:

| URL Scheme | Mode | Description |
|------------|------|-------------|
| `valkey://<user>:<pass>@<host>:<port>/<db>` | Standalone | Single Valkey node |
| `valkeys://<user>:<pass>@<host>:<port>/<db>` | Standalone + TLS | Single node with TLS |
| `valkey+cluster://<user>:<pass>@<host>:<port>` | Cluster | Valkey cluster |
| `valkeys+cluster://<user>:<pass>@<host>:<port>` | Cluster + TLS | Cluster with TLS |

Example `config.toml`:

```toml
[database]
cache_store = "valkey://localhost:6379/0"
```

The `valkey://` prefix is rewritten to `redis://` internally for `go-redis` URL parsing — the wire protocol is identical.

---

**Back to** [README](./README.md)
