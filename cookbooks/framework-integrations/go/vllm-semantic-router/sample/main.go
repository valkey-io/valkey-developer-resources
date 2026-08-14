package main

import (
	"context"
	"fmt"
	"os"
	"time"
)

func main() {
	client, err := NewRouterClient(os.Getenv("SEMANTIC_ROUTER_URL"), os.Getenv("SEMANTIC_ROUTER_MODEL"))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}

	ctx := context.Background()
	first, err := client.Chat(ctx, "What is the capital of France?")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	second, err := waitForCacheHit(ctx, client, "What is the capital of France?", time.Sleep)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	fmt.Printf("first request cache hit: %t\n", first.CacheHit)
	fmt.Printf("second request cache hit: %t\n", second.CacheHit)
	fmt.Printf("router response: %s\n", second.Content)
}
