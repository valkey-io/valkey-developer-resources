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

	cfg := config.NewClusterClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 7000}).
		WithRequestTimeout(10000)

	client, err := glide.NewClusterClient(cfg)
	if err != nil {
		fmt.Println("Connection error:", err)
		return
	}
	defer client.Close()

	fmt.Println("Connected to cluster")

	// Hash tags ensure same slot: {user}:1 and {user}:2
	atomicBatch := pipeline.NewClusterBatch(true).
		Set("{user}:1", "Alice").
		Set("{user}:2", "Bob").
		Get("{user}:1")

	results, err := client.Exec(ctx, *atomicBatch, true)
	if err != nil {
		fmt.Println("Atomic batch error:", err)
		return
	}
	fmt.Println("Atomic batch (same slot):", results)

	// Atomic batch with different slots fails with CROSSSLOT
	crossSlotBatch := pipeline.NewClusterBatch(true).
		Set("key1", "value1").
		Set("key2", "value2")

	_, err = client.Exec(ctx, *crossSlotBatch, true)
	if err != nil {
		fmt.Println("Expected CROSSSLOT error:", err)
	}

	// Non-atomic batch can span multiple slots
	pipelineBatch := pipeline.NewClusterBatch(false).
		Set("key1", "value1").
		Set("key2", "value2").
		Get("key1").
		Get("key2")

	results, err = client.Exec(ctx, *pipelineBatch, true)
	if err != nil {
		fmt.Println("Pipeline error:", err)
		return
	}
	fmt.Println("Pipeline (multi-slot):", results)

	// Cleanup using non-atomic batch for multi-slot delete
	cleanupBatch := pipeline.NewClusterBatch(false).
		Del([]string{"{user}:1", "{user}:2"}).
		Del([]string{"key1"}).
		Del([]string{"key2"})

	results, err = client.Exec(ctx, *cleanupBatch, true)
	if err != nil {
		fmt.Println("Cleanup error:", err)
		return
	}
	fmt.Println("Cleanup batch results:", results)
	fmt.Println("Cluster operations completed")
}
