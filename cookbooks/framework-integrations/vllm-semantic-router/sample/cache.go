package main

import (
	"context"
	"fmt"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
)

const (
	cacheIndex     = "semantic_cache_idx"
	cachePrefix    = "doc:"
	cacheThreshold = 0.85 // min cosine similarity for a cache HIT
)

// runCacheDemo mirrors the router's semantic cache backend (PR #1540): create
// an HNSW index, store a prompt/response pair with its embedding, then run a
// KNN lookup with a paraphrased query to demonstrate a cache hit.
func runCacheDemo(ctx context.Context, client *glide.Client) error {
	fmt.Println("== vLLM Semantic Router — Valkey cache demo ==")

	// Idempotent cleanup: drop a stale index and keys from a prior failed run
	// so re-runs start clean. Ignored if the index does not exist.
	_, _ = client.CustomCommand(ctx, []string{"FT.DROPINDEX", cacheIndex})
	deleteByPrefix(ctx, client, cachePrefix)

	if err := createCacheIndex(ctx, client); err != nil {
		return err
	}
	defer func() {
		_, _ = client.CustomCommand(ctx, []string{"FT.DROPINDEX", cacheIndex})
		deleteByPrefix(ctx, client, cachePrefix)
		fmt.Println("✓ Cleaned up index")
	}()
	fmt.Printf("✓ Created index %s\n", cacheIndex)

	question := "What is the capital of France?"
	answer := "The capital of France is Paris."
	if err := storeCacheEntry(ctx, client, "req-1", "gpt-4", question, answer); err != nil {
		return err
	}
	fmt.Printf("✓ Stored entry for: %q\n", question)

	// valkey-search indexes asynchronously; give it a moment before querying.
	time.Sleep(500 * time.Millisecond)

	paraphrase := "What's the capital city of France?"
	fmt.Printf("→ Searching with paraphrase: %q\n", paraphrase)
	response, similarity, hit, err := lookupCache(ctx, client, paraphrase)
	if err != nil {
		return err
	}
	if hit {
		fmt.Printf("✓ Cache HIT (similarity %.2f ≥ %.2f)\n", similarity, cacheThreshold)
		fmt.Printf("  cached response: %s\n", response)
	} else {
		fmt.Printf("✗ Cache MISS (best similarity %.2f < %.2f)\n", similarity, cacheThreshold)
	}
	return nil
}

// createCacheIndex issues the FT.CREATE the router uses for its cache: TAG
// fields for exact request/model lookup plus an HNSW VECTOR field for KNN.
func createCacheIndex(ctx context.Context, client *glide.Client) error {
	cmd := []string{
		"FT.CREATE", cacheIndex,
		"ON", "HASH",
		"PREFIX", "1", cachePrefix,
		"SCHEMA",
		"request_id", "TAG",
		"model", "TAG",
		"query", "TEXT",
		"embedding", "VECTOR", "HNSW", "10",
		"TYPE", "FLOAT32",
		"DIM", strconv.Itoa(embedDim),
		"DISTANCE_METRIC", "COSINE",
		"M", "16",
		"EF_CONSTRUCTION", "64",
		"timestamp", "NUMERIC",
	}
	if _, err := client.CustomCommand(ctx, cmd); err != nil {
		return fmt.Errorf("FT.CREATE failed (is the Search module loaded?): %w", err)
	}
	return nil
}

// storeCacheEntry writes a cache entry as a HASH and sets a TTL, matching the
// router's addEntry path (HSET + EXPIRE).
func storeCacheEntry(ctx context.Context, client *glide.Client, requestID, model, query, response string) error {
	key := cachePrefix + requestID
	embedding := float32ToBytes(stubEmbedding(query))
	hset := []string{
		"HSET", key,
		"request_id", requestID,
		"model", model,
		"query", query,
		"response_body", response,
		"embedding", string(embedding),
		"timestamp", strconv.FormatInt(time.Now().Unix(), 10),
	}
	if _, err := client.CustomCommand(ctx, hset); err != nil {
		return fmt.Errorf("HSET failed: %w", err)
	}
	// Set the TTL via the native typed Expire wrapper (EXPIRE under the hood).
	if _, err := client.Expire(ctx, key, time.Hour); err != nil {
		return fmt.Errorf("EXPIRE failed: %w", err)
	}
	return nil
}

// lookupCache runs the KNN search the router uses for cache reads and converts
// the cosine distance to a similarity score for the threshold check.
func lookupCache(ctx context.Context, client *glide.Client, query string) (response string, similarity float64, hit bool, err error) {
	embedding := float32ToBytes(stubEmbedding(query))
	cmd := []string{
		"FT.SEARCH", cacheIndex,
		"*=>[KNN 1 @embedding $vec AS vector_distance]",
		"RETURN", "2", "vector_distance", "response_body",
		"DIALECT", "2",
		"PARAMS", "2", "vec", string(embedding),
	}
	result, err := client.CustomCommand(ctx, cmd)
	if err != nil {
		return "", 0, false, fmt.Errorf("FT.SEARCH failed: %w", err)
	}

	docs := parseSearchDocs(result)
	if len(docs) == 0 {
		return "", 0, false, nil
	}
	best := docs[0]
	distance, _ := strconv.ParseFloat(fmt.Sprint(best["vector_distance"]), 64)
	similarity = cosineDistanceToSimilarity(distance)
	if similarity < cacheThreshold {
		return "", similarity, false, nil
	}
	return fmt.Sprint(best["response_body"]), similarity, true, nil
}
