// Package main demonstrates the Gorse-style Valkey cache patterns:
// sorted-set + hash time series and auto-detection of Valkey via INFO server.
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

// TimeSeriesPoint represents a single time series data point.
type TimeSeriesPoint struct {
	Name      string
	Value     float64
	Timestamp time.Time
}

// ValkeyCache implements the Gorse cache pattern: sorted-set time series
// with go-redis as the client. This mirrors the RedisValkey struct from
// gorse-io/gorse#1263.
type ValkeyCache struct {
	client *redis.Client
	prefix string
}

// NewValkeyCache creates a new cache instance connected to the given address.
func NewValkeyCache(addr string) *ValkeyCache {
	return &ValkeyCache{
		client: redis.NewClient(&redis.Options{Addr: addr}),
		prefix: "gorse_cache:",
	}
}

// Close closes the underlying Redis client connection.
func (v *ValkeyCache) Close() error {
	return v.client.Close()
}

// IsValkey checks the server INFO to determine if the connected server is Valkey.
func (v *ValkeyCache) IsValkey(ctx context.Context) (bool, error) {
	info, err := v.client.Info(ctx, "server").Result()
	if err != nil {
		return false, err
	}
	for _, line := range strings.Split(info, "\n") {
		if strings.TrimSpace(line) == "server_name:valkey" {
			return true, nil
		}
	}
	return false, nil
}

// AddTimeSeriesPoints stores time series points using sorted sets + hashes.
// Each series uses two keys:
//   - Sorted set (ts_index:{name}): score = timestamp_ms, member = timestamp_ms string
//   - Hash (ts_data:{name}): field = timestamp_ms string, value = float64 string
//
// ZADD naturally handles duplicate timestamps (score update = no-op for same member),
// and HSET naturally overwrites (last-write-wins), matching Redis TimeSeries LAST policy.
func (v *ValkeyCache) AddTimeSeriesPoints(ctx context.Context, points []TimeSeriesPoint) error {
	if len(points) == 0 {
		return nil
	}
	pipe := v.client.Pipeline()
	for _, point := range points {
		tsMsStr := strconv.FormatInt(point.Timestamp.UnixMilli(), 10)
		indexKey := v.prefix + "ts_index:" + point.Name
		dataKey := v.prefix + "ts_data:" + point.Name
		pipe.ZAdd(ctx, indexKey, redis.Z{Score: float64(point.Timestamp.UnixMilli()), Member: tsMsStr})
		pipe.HSet(ctx, dataKey, tsMsStr, strconv.FormatFloat(point.Value, 'g', -1, 64))
	}
	_, err := pipe.Exec(ctx)
	return err
}

// GetTimeSeriesPoints retrieves time series points within [begin, end] and
// aggregates them into buckets of the given duration, returning the last value
// per bucket. This mirrors Redis TS.RANGE with AGGREGATION last.
func (v *ValkeyCache) GetTimeSeriesPoints(ctx context.Context, name string, begin, end time.Time, bucketDuration time.Duration) ([]TimeSeriesPoint, error) {
	indexKey := v.prefix + "ts_index:" + name
	dataKey := v.prefix + "ts_data:" + name

	beginMs := begin.UnixMilli()
	endMs := end.UnixMilli()

	// Fetch all timestamps in range from the sorted set.
	members, err := v.client.ZRangeByScore(ctx, indexKey, &redis.ZRangeBy{
		Min: strconv.FormatInt(beginMs, 10),
		Max: strconv.FormatInt(endMs, 10),
	}).Result()
	if err != nil {
		return nil, err
	}
	if len(members) == 0 {
		return []TimeSeriesPoint{}, nil
	}

	// Fetch corresponding values from hash.
	vals, err := v.client.HMGet(ctx, dataKey, members...).Result()
	if err != nil {
		return nil, err
	}

	// Client-side bucket aggregation: last value per bucket.
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
		ts, err := strconv.ParseInt(member, 10, 64)
		if err != nil {
			continue
		}
		valStr, ok := vals[i].(string)
		if !ok {
			continue
		}
		val, err := strconv.ParseFloat(valStr, 64)
		if err != nil {
			continue
		}
		bucketKey := (ts / durationMs) * durationMs
		if existing, ok := buckets[bucketKey]; !ok || ts > existing.timestamp {
			buckets[bucketKey] = &bucketEntry{timestamp: ts, value: val}
		}
	}

	// Sort bucket keys and build result.
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

// Flush removes all keys with the cache prefix (for testing).
func (v *ValkeyCache) Flush(ctx context.Context) error {
	iter := v.client.Scan(ctx, 0, v.prefix+"*", 100).Iterator()
	for iter.Next(ctx) {
		v.client.Del(ctx, iter.Val())
	}
	return iter.Err()
}

func main() {
	addr := os.Getenv("VALKEY_ADDR")
	if addr == "" {
		addr = "127.0.0.1:6379"
	}

	cache := NewValkeyCache(addr)
	defer cache.Close()

	ctx := context.Background()

	// Detect server type
	isValkey, err := cache.IsValkey(ctx)
	if err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}
	if isValkey {
		fmt.Println("Connected to Valkey (server_name:valkey detected)")
	} else {
		fmt.Println("Connected to Redis (Valkey not detected — sorted-set TS still works)")
	}

	// Store 10 time series points (1 per second)
	baseTime := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)
	points := make([]TimeSeriesPoint, 10)
	for i := range 10 {
		points[i] = TimeSeriesPoint{
			Name:      "click_through_rate",
			Value:     float64(i + 1),
			Timestamp: baseTime.Add(time.Duration(i) * time.Second),
		}
	}

	if err := cache.AddTimeSeriesPoints(ctx, points); err != nil {
		log.Fatalf("Failed to add points: %v", err)
	}
	fmt.Printf("Stored %d time series points\n", len(points))

	// Query with 5-second bucket aggregation (last value per bucket)
	result, err := cache.GetTimeSeriesPoints(ctx, "click_through_rate",
		baseTime, baseTime.Add(9*time.Second), 5*time.Second)
	if err != nil {
		log.Fatalf("Failed to query: %v", err)
	}

	fmt.Printf("Queried 5-second buckets: %d results\n", len(result))
	for _, p := range result {
		fmt.Printf("  bucket %v → value: %f\n", p.Timestamp, p.Value)
	}

	// Clean up demo data
	if err := cache.Flush(ctx); err != nil {
		log.Fatalf("Failed to flush: %v", err)
	}

	fmt.Println("✅ Gorse-style Valkey cache patterns demonstrated successfully")
}
