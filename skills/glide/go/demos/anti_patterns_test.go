package main

import (
	"context"
	"os"
	"testing"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)

// TestUnsafeTypeAssertion proves that unsafe type assertions panic
func TestUnsafeTypeAssertion(t *testing.T) {
	ctx := context.Background()
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, err := glide.NewClient(cfg)
	if err != nil {
		t.Skip("Skipping test - no Valkey server available")
	}
	defer client.Close()

	// Create batch with mixed return types
	batch := pipeline.NewStandaloneBatch(false).
		Set("key1", "value1"). // Returns "OK" (string)
		Incr("counter")         // Returns int64

	results, err := client.Exec(ctx, *batch, false)
	if err != nil {
		t.Fatalf("Exec failed: %v", err)
	}

	// Test that unsafe assertion panics
	defer func() {
		if r := recover(); r == nil {
			t.Error("Expected panic from unsafe type assertion, but didn't panic")
		}
	}()

	// ❌ This should panic on second iteration
	for _, result := range results {
		_ = result.(string) // PANIC on int64 result
	}
}

// TestSafeTypeAssertion proves that safe type assertions don't panic
func TestSafeTypeAssertion(t *testing.T) {
	ctx := context.Background()
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, err := glide.NewClient(cfg)
	if err != nil {
		t.Skip("Skipping test - no Valkey server available")
	}
	defer client.Close()

	// Create batch with mixed return types
	batch := pipeline.NewStandaloneBatch(false).
		Set("key1", "value1"). // Returns "OK" (string)
		Incr("counter")         // Returns int64

	results, err := client.Exec(ctx, *batch, false)
	if err != nil {
		t.Fatalf("Exec failed: %v", err)
	}

	// ✅ Safe type assertion - no panic
	stringCount := 0
	intCount := 0

	for _, result := range results {
		if _, ok := result.(string); ok {
			stringCount++
		}
		if _, ok := result.(int64); ok {
			intCount++
		}
	}

	if stringCount != 1 {
		t.Errorf("Expected 1 string result, got %d", stringCount)
	}
	if intCount != 1 {
		t.Errorf("Expected 1 int64 result, got %d", intCount)
	}
}

// TestMissingErrorCheck demonstrates why error checking is critical
func TestMissingErrorCheck(t *testing.T) {
	// Try to connect to non-existent server
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "invalid-host-that-does-not-exist", Port: 9999})

	// ❌ Wrong: ignoring error
	client, _ := glide.NewClient(cfg)

	// This will be nil because connection failed
	if client == nil {
		t.Log("✓ Client is nil when error is ignored (demonstrates the problem)")
	} else {
		defer client.Close()
		t.Error("Expected nil client from failed connection")
	}

	// ✅ Correct: checking error
	client2, err := glide.NewClient(cfg)
	if err != nil {
		t.Logf("✓ Caught connection error as expected: %v", err)
	} else {
		defer client2.Close()
		t.Error("Expected error from invalid connection")
	}
}

// TestContextCancellation proves context cancellation works
func TestContextCancellation(t *testing.T) {
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, err := glide.NewClient(cfg)
	if err != nil {
		t.Skip("Skipping test - no Valkey server available")
	}
	defer client.Close()

	// Create cancelled context
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	// Operation should fail with context error
	_, err = client.Get(ctx, "key")
	if err == nil {
		t.Error("Expected error from cancelled context")
	}

	if ctx.Err() != context.Canceled {
		t.Errorf("Expected context.Canceled, got %v", ctx.Err())
	}

	t.Logf("✓ Context cancellation works as expected: %v", err)
}

// TestBatchDereference - compile-time check (won't compile if wrong)
func TestBatchDereference(t *testing.T) {
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, err := glide.NewClient(cfg)
	if err != nil {
		t.Skip("Skipping test - no Valkey server available")
	}
	defer client.Close()

	batch := pipeline.NewStandaloneBatch(false).
		Set("key1", "value1")

	// ✅ Correct: dereference with *
	_, err = client.Exec(context.Background(), *batch, true)
	if err != nil {
		t.Logf("Exec error (may be expected): %v", err)
	}

	// ❌ Wrong: without dereference (won't compile)
	// _, err = client.Exec(context.Background(), batch, true)
	// Compile error: cannot use batch (variable of type *pipeline.StandaloneBatch)
}
