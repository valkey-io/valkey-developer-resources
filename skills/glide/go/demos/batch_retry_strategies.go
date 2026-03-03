package main

import (
	"context"
	"fmt"
	"os"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)

func main() {
	ctx := context.Background()
	host := os.Getenv("VALKEY_HOST")
	if host == "" {
		host = "localhost"
	}

	cfg := config.NewClusterClientConfiguration().
		WithAddress(&config.NodeAddress{Host: host, Port: 7000}).
		WithAddress(&config.NodeAddress{Host: host, Port: 7001}).
		WithAddress(&config.NodeAddress{Host: host, Port: 7002}).
		WithRequestTimeout(10000)

	client, err := glide.NewClusterClient(cfg)
	if err != nil {
		fmt.Println("Connection error:", err)
		return
	}
	defer client.Close()

	fmt.Println("=== Batch Operation Retry Strategies ===\n")

	// Scenario 1: retryServerError - Cluster resharding/server load
	fmt.Println("1. RETRY SERVER ERRORS (cluster resharding, server under load)")
	fmt.Println("   Use when: Transient server errors, TRYAGAIN responses")
	fmt.Println("   Trade-off: May reorder commands within batch\n")

	batch1 := pipeline.NewClusterBatch(false).
		Set("{user:1}:name", "Alice").
		Set("{user:1}:email", "alice@example.com").
		Get("{user:1}:name")

	options1 := pipeline.NewClusterBatchOptions().
		WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
			WithRetryServerError(true).
			WithRetryConnectionError(false))

	results, err := client.ExecWithOptions(ctx, *batch1, true, *options1)
	if err != nil {
		fmt.Println("   ✗ Error:", err)
	} else {
		fmt.Printf("   ✓ Results: %v\n\n", results)
	}

	// Scenario 2: retryConnectionError - Network instability
	fmt.Println("2. RETRY CONNECTION ERRORS (network instability, failover)")
	fmt.Println("   Use when: Network issues, cluster node failover")
	fmt.Println("   Trade-off: May duplicate entire batch\n")

	batch2 := pipeline.NewClusterBatch(false).
		Set("{user:2}:name", "Bob").
		Set("{user:2}:email", "bob@example.com").
		Get("{user:2}:name")

	options2 := pipeline.NewClusterBatchOptions().
		WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
			WithRetryServerError(false).
			WithRetryConnectionError(true))

	results, err = client.ExecWithOptions(ctx, *batch2, true, *options2)
	if err != nil {
		fmt.Println("   ✗ Error:", err)
	} else {
		fmt.Printf("   ✓ Results: %v\n\n", results)
	}

	// Scenario 3: Both retries - Maximum resilience
	fmt.Println("3. RETRY BOTH (maximum resilience)")
	fmt.Println("   Use when: High availability required, idempotent operations")
	fmt.Println("   Trade-off: Possible reordering + duplication\n")

	batch3 := pipeline.NewClusterBatch(false).
		Set("{user:3}:name", "Charlie").
		Set("{user:3}:email", "charlie@example.com").
		Get("{user:3}:name")

	options3 := pipeline.NewClusterBatchOptions().
		WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
			WithRetryServerError(true).
			WithRetryConnectionError(true))

	results, err = client.ExecWithOptions(ctx, *batch3, true, *options3)
	if err != nil {
		fmt.Println("   ✗ Error:", err)
	} else {
		fmt.Printf("   ✓ Results: %v\n\n", results)
	}

	// Scenario 4: No retries - Strict latency requirements
	fmt.Println("4. NO RETRIES (strict latency, non-idempotent)")
	fmt.Println("   Use when: SLA-bound operations, already have app-level retry")
	fmt.Println("   Trade-off: Fail fast on any error\n")

	batch4 := pipeline.NewClusterBatch(false).
		Set("{user:4}:name", "Diana").
		Set("{user:4}:email", "diana@example.com").
		Get("{user:4}:name")

	options4 := pipeline.NewClusterBatchOptions().
		WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
			WithRetryServerError(false).
			WithRetryConnectionError(false))

	results, err = client.ExecWithOptions(ctx, *batch4, true, *options4)
	if err != nil {
		fmt.Println("   ✗ Error:", err)
	} else {
		fmt.Printf("   ✓ Results: %v\n\n", results)
	}

	fmt.Println("=== Summary ===")
	fmt.Println("✓ RetryServerError: Cluster resharding, server load")
	fmt.Println("✓ RetryConnectionError: Network issues, failover")
	fmt.Println("✓ Both: Maximum resilience (idempotent ops)")
	fmt.Println("✓ Neither: Strict latency, non-idempotent, app-level retry")
}
