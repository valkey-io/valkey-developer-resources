package main

import (
	"context"
	"fmt"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/constants"
	"github.com/valkey-io/valkey-glide/go/v2/options"
	"github.com/valkey-io/valkey-glide/go/v2/servermodules/glideft"
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
	_, _ = glideft.FtDropIndex(ctx, client, cacheIndex)
	deleteByPrefix(ctx, client, cachePrefix)

	if err := createCacheIndex(ctx, client); err != nil {
		return err
	}
	defer func() {
		_, _ = glideft.FtDropIndex(ctx, client, cacheIndex)
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
// fields for exact request/model lookup plus an HNSW VECTOR field for KNN. The
// typed glideft/options API builds the command, so field names, the vector
// algorithm, and HNSW parameters are checked at compile time.
func createCacheIndex(ctx context.Context, client *glide.Client) error {
	schema := []options.Field{
		options.NewTagField("request_id"),
		options.NewTagField("model"),
		options.NewTextField("query"),
		options.NewVectorFieldHNSW("embedding", constants.DistanceMetricCosine, embedDim).
			SetNumberOfEdges(16).                 // HNSW M: links per node
			SetVectorsExaminedOnConstruction(64), // HNSW EF_CONSTRUCTION
		options.NewNumericField("timestamp"),
	}
	opts := &options.FtCreateOptions{
		DataType: constants.IndexDataTypeHash,
		Prefixes: []string{cachePrefix},
	}
	if _, err := glideft.FtCreate(ctx, client, cacheIndex, schema, opts); err != nil {
		return fmt.Errorf("FT.CREATE failed (is the Search module loaded?): %w", err)
	}
	return nil
}

// storeCacheEntry writes a cache entry as a HASH and sets a TTL, matching the
// router's addEntry path (HSET + EXPIRE).
func storeCacheEntry(ctx context.Context, client *glide.Client, requestID, model, query, response string) error {
	key := cachePrefix + requestID
	// string(embedding) intentionally coerces the raw little-endian FLOAT32
	// bytes into a string without re-encoding: Go's string([]byte) preserves
	// the exact bytes and RESP is binary-safe, so the VECTOR field round-trips
	// unchanged. Do not "fix" this to a textual encoding. (Same pattern in
	// vectorstore.go and memory.go.)
	embedding := float32ToBytes(stubEmbedding(query))
	fields := map[string]string{
		"request_id":    requestID,
		"model":         model,
		"query":         query,
		"response_body": response,
		"embedding":     string(embedding),
		"timestamp":     strconv.FormatInt(time.Now().Unix(), 10),
	}
	if _, err := client.HSet(ctx, key, fields); err != nil {
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
	dialect := 2
	searchOpts := &options.FtSearchOptions{
		ReturnFields: []options.FtSearchReturnField{
			{FieldIdentifier: "vector_distance"},
			{FieldIdentifier: "response_body"},
		},
		Params:  []options.FtSearchParam{{Key: "vec", Value: string(embedding)}},
		Dialect: &dialect,
	}
	result, err := glideft.FtSearch(ctx, client, cacheIndex,
		"*=>[KNN 1 @embedding $vec AS vector_distance]", searchOpts)
	if err != nil {
		return "", 0, false, fmt.Errorf("FT.SEARCH failed: %w", err)
	}
	if len(result.Documents) == 0 {
		return "", 0, false, nil
	}

	best := result.Documents[0].Fields
	// A parse failure here must not be discarded: cosineDistanceToSimilarity(0)
	// == 1.0, so silently defaulting distance to 0 would report a false
	// perfect match instead of surfacing that the field was missing or
	// malformed.
	distance, err := strconv.ParseFloat(fmt.Sprint(best["vector_distance"]), 64)
	if err != nil {
		return "", 0, false, fmt.Errorf("vector_distance field missing or non-numeric: %w", err)
	}
	similarity = cosineDistanceToSimilarity(distance)
	if similarity < cacheThreshold {
		return "", similarity, false, nil
	}
	return fmt.Sprint(best["response_body"]), similarity, true, nil
}
