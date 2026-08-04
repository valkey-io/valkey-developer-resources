package main

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestCache(t *testing.T) *ValkeyCache {
	t.Helper()
	addr := os.Getenv("VALKEY_ADDR")
	if addr == "" {
		addr = "127.0.0.1:6379"
	}
	cache := NewValkeyCache(addr)
	ctx := context.Background()
	// Verify connectivity
	_, err := cache.client.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Valkey not available at %s: %v", addr, err)
	}
	// Clean up before and after
	_ = cache.Flush(ctx)
	t.Cleanup(func() {
		_ = cache.Flush(ctx)
		_ = cache.Close()
	})
	return cache
}

func TestIsValkey(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()

	isValkey, err := cache.IsValkey(ctx)
	require.NoError(t, err)
	// When running against valkey-bundle, this should be true.
	assert.True(t, isValkey, "expected server to be Valkey")
}

func TestAddTimeSeriesPointsEmpty(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()

	// nil should not error
	err := cache.AddTimeSeriesPoints(ctx, nil)
	assert.NoError(t, err)

	// empty slice should not error
	err = cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{})
	assert.NoError(t, err)
}

func TestAddAndQuerySinglePoint(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 3, 1, 12, 0, 0, 0, time.UTC)

	err := cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{
		{Name: "single", Value: 42.5, Timestamp: ts},
	})
	require.NoError(t, err)

	points, err := cache.GetTimeSeriesPoints(ctx, "single", ts, ts, time.Second)
	require.NoError(t, err)
	require.Len(t, points, 1)
	assert.Equal(t, 42.5, points[0].Value)
	assert.Equal(t, "single", points[0].Name)
}

func TestDuplicateTimestamp(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 6, 15, 0, 0, 0, 0, time.UTC)

	// Write initial value
	err := cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{
		{Name: "dup", Value: 100, Timestamp: ts},
	})
	require.NoError(t, err)

	// Overwrite with new value at same timestamp (last-write-wins)
	err = cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{
		{Name: "dup", Value: 200, Timestamp: ts},
	})
	require.NoError(t, err)

	points, err := cache.GetTimeSeriesPoints(ctx, "dup", ts, ts, time.Second)
	require.NoError(t, err)
	require.Len(t, points, 1)
	assert.Equal(t, float64(200), points[0].Value)
}

func TestEmptyRange(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

	// Add a point
	err := cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{
		{Name: "empty_range", Value: 1, Timestamp: ts},
	})
	require.NoError(t, err)

	// Query a range with no points
	points, err := cache.GetTimeSeriesPoints(ctx, "empty_range",
		ts.Add(10*time.Second), ts.Add(20*time.Second), time.Second)
	require.NoError(t, err)
	assert.Empty(t, points)
}

func TestMultipleSeriesIsolation(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

	err := cache.AddTimeSeriesPoints(ctx, []TimeSeriesPoint{
		{Name: "series_x", Value: 10, Timestamp: ts.Add(1 * time.Second)},
		{Name: "series_x", Value: 20, Timestamp: ts.Add(2 * time.Second)},
		{Name: "series_y", Value: 30, Timestamp: ts.Add(1 * time.Second)},
		{Name: "series_y", Value: 40, Timestamp: ts.Add(2 * time.Second)},
	})
	require.NoError(t, err)

	pointsX, err := cache.GetTimeSeriesPoints(ctx, "series_x", ts, ts.Add(3*time.Second), time.Second)
	require.NoError(t, err)
	assert.Equal(t, []TimeSeriesPoint{
		{Name: "series_x", Value: 10, Timestamp: ts.Add(1 * time.Second)},
		{Name: "series_x", Value: 20, Timestamp: ts.Add(2 * time.Second)},
	}, pointsX)

	pointsY, err := cache.GetTimeSeriesPoints(ctx, "series_y", ts, ts.Add(3*time.Second), time.Second)
	require.NoError(t, err)
	assert.Equal(t, []TimeSeriesPoint{
		{Name: "series_y", Value: 30, Timestamp: ts.Add(1 * time.Second)},
		{Name: "series_y", Value: 40, Timestamp: ts.Add(2 * time.Second)},
	}, pointsY)
}

func TestBucketAggregation(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

	// Add 10 points, 1 per second
	points := make([]TimeSeriesPoint, 10)
	for i := range 10 {
		points[i] = TimeSeriesPoint{
			Name:      "agg",
			Value:     float64(i + 1),
			Timestamp: ts.Add(time.Duration(i) * time.Second),
		}
	}
	err := cache.AddTimeSeriesPoints(ctx, points)
	require.NoError(t, err)

	// Query with 5-second buckets: [0-4] and [5-9]
	result, err := cache.GetTimeSeriesPoints(ctx, "agg", ts, ts.Add(9*time.Second), 5*time.Second)
	require.NoError(t, err)
	require.Len(t, result, 2)

	// First bucket [0s,5s): last value is at 4s = value 5
	assert.Equal(t, float64(5), result[0].Value)
	assert.Equal(t, ts, result[0].Timestamp)

	// Second bucket [5s,10s): last value is at 9s = value 10
	assert.Equal(t, float64(10), result[1].Value)
	assert.Equal(t, ts.Add(5*time.Second), result[1].Timestamp)
}

func TestBatchAdd(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

	// Batch add 100 points
	batch := make([]TimeSeriesPoint, 100)
	for i := range 100 {
		batch[i] = TimeSeriesPoint{
			Name:      "batch_ts",
			Value:     float64(i),
			Timestamp: ts.Add(time.Duration(i) * time.Second),
		}
	}
	err := cache.AddTimeSeriesPoints(ctx, batch)
	require.NoError(t, err)

	// Query full range with 10-second buckets
	points, err := cache.GetTimeSeriesPoints(ctx, "batch_ts", ts, ts.Add(99*time.Second), 10*time.Second)
	require.NoError(t, err)
	assert.Len(t, points, 10)

	// Last bucket should have the highest value in its range (99)
	assert.Equal(t, float64(99), points[9].Value)
}

func TestNonExistentSeries(t *testing.T) {
	cache := newTestCache(t)
	ctx := context.Background()
	ts := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

	// Query a series that doesn't exist
	points, err := cache.GetTimeSeriesPoints(ctx, "does_not_exist", ts, ts.Add(time.Hour), time.Second)
	require.NoError(t, err)
	assert.Empty(t, points)
}
