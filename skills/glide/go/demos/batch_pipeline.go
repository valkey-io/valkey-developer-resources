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

	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379}).
		WithRequestTimeout(10000)

	client, err := glide.NewClient(cfg)
	if err != nil {
		fmt.Println("Connection error:", err)
		return
	}
	defer client.Close()

	// Pipeline (non-atomic): bulk independent operations
	pipelineBatch := pipeline.NewStandaloneBatch(false).
		Set("user:1", "Alice").
		Set("user:2", "Bob").
		Get("user:1").
		Get("user:2")

	results, err := client.Exec(ctx, *pipelineBatch, true)
	if err != nil {
		fmt.Println("Pipeline error:", err)
		return
	}
	fmt.Println("Pipeline results:", results)

	// Transaction (atomic): consistent multi-key update
	transaction := pipeline.NewStandaloneBatch(true).
		Set("counter", "0").
		Incr("counter").
		Incr("counter").
		Get("counter")

	results, err = client.Exec(ctx, *transaction, true)
	if err != nil {
		fmt.Println("Transaction error:", err)
		return
	}
	fmt.Println("Transaction results:", results)

	fmt.Println("Batch/pipeline operations completed")
}
