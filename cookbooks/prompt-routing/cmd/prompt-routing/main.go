/*
prompt-routing demonstrates Valkey as llm-d's shared KV-cache routing index,
the index that prompt routing is built on.

llm-d's router (the Endpoint Picker) keeps a map from KV-cache block keys to the
model-server pods that hold those blocks. When the backend is Valkey, that map
lives in Valkey instead of in a single router replica's memory, so every router
replica reads and writes one shared index. This program drives llm-d's real
indexer library (github.com/llm-d/llm-d-kv-cache) against Valkey, so the keys it
writes are exactly what a live router would store.

It is deliberately small: it exercises the index backend directly (Add, Lookup,
Evict) rather than standing up model servers, a tokenizer, or GPUs. The full
routing+serving path — servers emitting KV-cache events, the router scoring live
requests — is a Kubernetes/GPU system and out of scope for this recipe.

Each subcommand opens a fresh connection and does one step. Because the index
lives in Valkey, running the steps as separate processes mirrors separate router
replicas sharing one index: state recorded by one run is visible to the next.

Usage:

	prompt-routing record    # a server reports the blocks it cached
	prompt-routing lookup    # the router looks up who holds the conversation
	prompt-routing evict     # the server evicts the first block; the prefix chain breaks
*/
package main

import (
	"context"
	"fmt"
	"os"

	"github.com/llm-d/llm-d-kv-cache/pkg/kvcache/kvblock"
)

// conversation stands in for one chat's prefix. A prompt is split into
// fixed-size token blocks; each block's hash depends on its content and every
// block before it, so a shared prefix yields a shared run of block hashes.
var conversation = []kvblock.BlockHash{1001, 1002, 1003}

// serverA is one model server (pod) behind the router.
var serverA = []kvblock.PodEntry{{PodIdentifier: "vllm-a", DeviceTier: "gpu"}}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: prompt-routing <record|lookup|evict>")
		os.Exit(2)
	}
	if err := run(context.Background(), os.Args[1]); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

// valkeyURL builds the index address from VALKEY_HOST / VALKEY_PORT, falling
// back to localhost. CI sets these to point at its Valkey service container.
func valkeyURL() string {
	host := os.Getenv("VALKEY_HOST")
	if host == "" {
		host = "127.0.0.1"
	}
	port := os.Getenv("VALKEY_PORT")
	if port == "" {
		port = "6379"
	}
	return fmt.Sprintf("valkey://%s:%s", host, port)
}

func run(ctx context.Context, step string) error {
	// NewValkeyIndex opens the same Valkey-backed index the router's Endpoint
	// Picker uses when configured with a Valkey backend.
	index, err := kvblock.NewValkeyIndex(&kvblock.RedisIndexConfig{Address: valkeyURL()})
	if err != nil {
		return fmt.Errorf("connect to the routing index at %s: %w", valkeyURL(), err)
	}

	switch step {
	case "record":
		return record(ctx, index)
	case "lookup":
		return lookup(ctx, index)
	case "evict":
		return evict(ctx, index)
	default:
		return fmt.Errorf("unknown step %q (want record, lookup, or evict)", step)
	}
}

// record stores that server vllm-a holds every block of the conversation. In
// llm-d a server reports this over a KV-cache event stream; here we write the
// same block -> pod entries straight into the shared index.
func record(ctx context.Context, index kvblock.Index) error {
	if err := index.Add(ctx, conversation, conversation, serverA); err != nil {
		return fmt.Errorf("record cached blocks: %w", err)
	}
	fmt.Printf("server vllm-a recorded %d cached blocks for the conversation\n", len(conversation))
	return nil
}

// lookup is the router's "who holds this prefix?" query. Passing nil as the pod
// filter means "no filter — return every server that holds each block".
func lookup(ctx context.Context, index kvblock.Index) error {
	hits, err := index.Lookup(ctx, conversation, nil)
	if err != nil {
		return fmt.Errorf("router lookup: %w", err)
	}
	for _, block := range conversation {
		fmt.Printf("block %d is cached on %v\n", uint64(block), podNames(hits[block]))
	}
	fmt.Printf("the router can rely on a cached prefix of %d block(s)\n", prefixLen(hits))
	return nil
}

// evict removes the first block from server vllm-a (as if under memory
// pressure) and shows the router's reliable cached prefix afterward. The prefix
// is a chain: it counts only up to the first missing block, so evicting the
// front drops the reliable length to zero even though later blocks remain.
func evict(ctx context.Context, index kvblock.Index) error {
	if err := index.Evict(ctx, conversation[0], kvblock.RequestKey, serverA); err != nil {
		return fmt.Errorf("evict first block: %w", err)
	}
	hits, err := index.Lookup(ctx, conversation, nil)
	if err != nil {
		return fmt.Errorf("router lookup after eviction: %w", err)
	}
	fmt.Printf("after vllm-a evicts the first block, the router can rely on %d block(s)\n", prefixLen(hits))
	return nil
}

// prefixLen counts the leading run of blocks that have at least one holder —
// the cached prefix the scorer can rely on.
func prefixLen(hits map[kvblock.BlockHash][]kvblock.PodEntry) int {
	n := 0
	for _, block := range conversation {
		if len(hits[block]) == 0 {
			break
		}
		n++
	}
	return n
}

// podNames extracts pod identifiers from a block's index entries for display.
func podNames(entries []kvblock.PodEntry) []string {
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.PodIdentifier)
	}
	return names
}
