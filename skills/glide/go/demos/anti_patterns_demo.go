package main

import (
	"context"
	"fmt"
	"os"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)

// This file demonstrates ANTI-PATTERNS to avoid in Go GLIDE code
// These examples intentionally show what NOT to do

func main() {
	fmt.Println("=== Go GLIDE Anti-Pattern Tests ===\n")

	testUnsafeTypeAssertion()
	testMissingErrorCheck()
	testNoDereferenceBatch()
	testWrongBatchType()
}

// Anti-Pattern 1: Unsafe type assertion (will panic)
func testUnsafeTypeAssertion() {
	fmt.Println("Test 1: Unsafe Type Assertion")
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("✓ Caught panic as expected: %v\n\n", r)
		}
	}()

	ctx := context.Background()
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, err := glide.NewClient(cfg)
	if err != nil {
		fmt.Printf("✓ Connection failed (expected if no server): %v\n\n", err)
		return
	}
	defer client.Close()

	// Set a string value
	client.Set(ctx, "test_key", "string_value")

	// Create batch that returns mixed types
	batch := pipeline.NewStandaloneBatch(false).
		Set("key1", "value1").
		Incr("counter")

	results, _ := client.Exec(ctx, *batch, false)

	// ❌ WRONG: Unsafe assertion - assumes all results are strings
	// This will panic when it hits the int64 result from Incr
	for i, result := range results {
		str := result.(string) // PANIC HERE on second iteration
		fmt.Printf("Result %d: %s\n", i, str)
	}
}

// Anti-Pattern 2: Ignoring error returns
func testMissingErrorCheck() {
	fmt.Println("Test 2: Missing Error Check")

	ctx := context.Background()
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379})

	client, _ := glide.NewClient(cfg) // ❌ WRONG: Ignoring error
	if client == nil {
		fmt.Println("✓ Client is nil (expected if no server)\n")
		return
	}
	defer client.Close()

	// ❌ WRONG: Not checking error
	client.Set(ctx, "key", "value") // What if this fails?

	// ❌ WRONG: Not checking error
	value, _ := client.Get(ctx, "key") // What if key doesn't exist?
	fmt.Printf("✓ Got value (may be nil): %v\n\n", value)
}

// Anti-Pattern 3: Forgetting to dereference batch
func testNoDereferenceBatch() {
	fmt.Println("Test 3: Not Dereferencing Batch")

	// ❌ WRONG: Passing batch without dereferencing
	// This won't compile - demonstrates the error
	// 
	// batch := pipeline.NewStandaloneBatch(false)
	// results, err := client.Exec(ctx, batch, true)
	// 
	// Error: cannot use batch (variable of type *pipeline.StandaloneBatch) 
	//        as pipeline.StandaloneBatch value

	fmt.Println("✓ Compilation would fail without * dereference")
	fmt.Println("  Correct: client.Exec(ctx, *batch, true)")
	fmt.Println("  Wrong:   client.Exec(ctx, batch, true)\n")
}

// Anti-Pattern 4: Using wrong batch type for client
func testWrongBatchType() {
	fmt.Println("Test 4: Wrong Batch Type for Client")

	// ❌ WRONG: Using StandaloneBatch with ClusterClient
	// This won't compile - type mismatch
	// 
	// clusterClient, _ := glide.NewClusterClient(cfg)
	// standaloneBatch := pipeline.NewStandaloneBatch(false)
	// results, err := clusterClient.Exec(ctx, *standaloneBatch, true)
	// 
	// Error: cannot use *standaloneBatch (variable of type pipeline.StandaloneBatch) 
	//        as pipeline.ClusterBatch value

	fmt.Println("✓ Compilation would fail with wrong batch type")
	fmt.Println("  Standalone client needs: pipeline.NewStandaloneBatch()")
	fmt.Println("  Cluster client needs:    pipeline.NewClusterBatch()\n")
}
