// Command sample demonstrates the three Valkey backends added to the vLLM
// Semantic Router — semantic cache, RAG vector store, and agentic memory —
// using the same valkey-glide commands the router issues (FT.CREATE, FT.SEARCH,
// HSET, HSETNX, HINCRBY). It uses deterministic stub embeddings so it runs
// without a GPU or model download.
//
// Usage:
//
//	go run . cache         # semantic cache backend (cookbook 01)
//	go run . vectorstore   # RAG vector store backend (cookbook 02)
//	go run . memory        # agentic memory backend (cookbook 03)
//
// Requires a Valkey instance with the Search module (valkey/valkey-bundle).
// Connection is configured via VALKEY_HOST (default localhost) and VALKEY_PORT
// (default 6379).
package main

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("usage: go run . [cache|vectorstore|memory]")
		os.Exit(2)
	}

	client, err := connect()
	if err != nil {
		fmt.Printf("✗ Failed to connect to Valkey: %v\n", err)
		fmt.Println("  Ensure Valkey with the Search module is running:")
		fmt.Println("    docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:9.1.0")
		os.Exit(1)
	}
	defer client.Close()

	ctx := context.Background()
	var demoErr error
	switch os.Args[1] {
	case "cache":
		demoErr = runCacheDemo(ctx, client)
	case "vectorstore":
		demoErr = runVectorStoreDemo(ctx, client)
	case "memory":
		demoErr = runMemoryDemo(ctx, client)
	default:
		fmt.Printf("unknown demo %q (use cache, vectorstore, or memory)\n", os.Args[1])
		os.Exit(2)
	}

	if demoErr != nil {
		fmt.Printf("\n✗ Demo failed: %v\n", demoErr)
		os.Exit(1)
	}
}

// connect builds a valkey-glide client from VALKEY_HOST / VALKEY_PORT and
// verifies connectivity with PING. An explicit request timeout is set because
// the GLIDE default (250 ms) is too aggressive for anyone not on localhost.
func connect() (*glide.Client, error) {
	host := getenv("VALKEY_HOST", "localhost")
	port := 6379
	if p := os.Getenv("VALKEY_PORT"); p != "" {
		if v, err := strconv.Atoi(p); err == nil {
			port = v
		}
	}

	clientConfig := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: host, Port: port}).
		WithRequestTimeout(5 * time.Second) // tune for your network latency
	// ⚠️ This sample connects without authentication or TLS for local development.
	// For production: add WithCredentials() and WithUseTLS(true) to the config above.

	client, err := glide.NewClient(clientConfig)
	if err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := client.Ping(ctx); err != nil {
		client.Close()
		return nil, err
	}
	fmt.Printf("✓ Connected to Valkey at %s:%d\n", host, port)
	return client, nil
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
