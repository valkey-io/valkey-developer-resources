package main

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
)

const (
	memIndex  = "mem_idx"
	memPrefix = "mem:"
)

// memory is a stored agentic memory, mirroring the fields the router persists.
type memory struct {
	id, userID, content, memType string
}

var aliceMemories = []memory{
	{"m1", "alice", "alice prefers dark mode in all applications", "semantic"},
	{"m2", "alice", "alice's preferred programming language is Go", "semantic"},
	{"m3", "alice", "to deploy, alice runs make deploy in the project root", "procedural"},
}

// runMemoryDemo mirrors the router's agentic memory backend (PR #1739): atomic
// store (HSETNX), user-scoped vector retrieval, atomic access tracking
// (HINCRBY), and scoped deletion.
func runMemoryDemo(ctx context.Context, client *glide.Client) error {
	fmt.Println("== vLLM Semantic Router — Valkey agentic memory demo ==")

	// Idempotent cleanup from any prior run.
	_, _ = client.CustomCommand(ctx, []string{"FT.DROPINDEX", memIndex})
	deleteByPrefix(ctx, client, memPrefix)

	if err := createMemoryIndex(ctx, client); err != nil {
		return err
	}
	defer func() {
		_, _ = client.CustomCommand(ctx, []string{"FT.DROPINDEX", memIndex})
		deleteByPrefix(ctx, client, memPrefix)
		fmt.Println("✓ Cleaned up index")
	}()
	fmt.Printf("✓ Created index %s\n", memIndex)

	for _, m := range aliceMemories {
		if err := storeMemory(ctx, client, m); err != nil {
			return err
		}
	}
	fmt.Printf("✓ Stored %d memories for user %q\n", len(aliceMemories), "alice")

	time.Sleep(500 * time.Millisecond) // allow async indexing

	fmt.Println("→ Retrieve: \"what does the user prefer?\"")
	results, err := retrieveMemory(ctx, client, "alice", "what does the user prefer?", 1)
	if err != nil {
		return err
	}
	if len(results) > 0 {
		fmt.Printf("  [%.2f] %s\n", results[0].score, results[0].content)
	} else {
		fmt.Println("  (no results)")
	}

	// User isolation: bob's query must never see alice's memories.
	bobResults, err := retrieveMemory(ctx, client, "bob", "what does the user prefer?", 5)
	if err != nil {
		return err
	}
	fmt.Printf("✓ User isolation: %q sees %d of alice's memories\n", "bob", len(bobResults))

	// Atomic access tracking via HINCRBY.
	count, err := recordAccess(ctx, client, "m1")
	if err != nil {
		return err
	}
	fmt.Printf("✓ Access count incremented to %d after retrieval\n", count)

	// Scoped deletion: remove everything for alice.
	deleted, err := forgetByUser(ctx, client, "alice")
	if err != nil {
		return err
	}
	fmt.Printf("✓ ForgetByScope deleted %d memories for %q\n", deleted, "alice")
	return nil
}

func createMemoryIndex(ctx context.Context, client *glide.Client) error {
	cmd := []string{
		"FT.CREATE", memIndex,
		"ON", "HASH",
		"PREFIX", "1", memPrefix,
		"SCHEMA",
		"id", "TAG",
		"user_id", "TAG",
		"project_id", "TAG",
		"memory_type", "TAG",
		"content", "TEXT",
		"source", "TAG",
		"embedding", "VECTOR", "HNSW", "10",
		"TYPE", "FLOAT32",
		"DIM", strconv.Itoa(embedDim),
		"DISTANCE_METRIC", "COSINE",
		"M", "16",
		"EF_CONSTRUCTION", "256",
		"created_at", "NUMERIC", "SORTABLE",
		"updated_at", "NUMERIC",
		"access_count", "NUMERIC",
		"importance", "NUMERIC",
	}
	if _, err := client.CustomCommand(ctx, cmd); err != nil {
		return fmt.Errorf("FT.CREATE failed (is the Search module loaded?): %w", err)
	}
	return nil
}

// storeMemory stores a memory atomically: HSETNX reserves the id (failing if it
// already exists), then HSET writes the fields. This avoids the check-then-set
// race the router guards against.
func storeMemory(ctx context.Context, client *glide.Client, m memory) error {
	key := memPrefix + m.id
	reserved, err := client.HSetNX(ctx, key, "id", m.id)
	if err != nil {
		return fmt.Errorf("HSETNX failed: %w", err)
	}
	if !reserved {
		return fmt.Errorf("memory %q already exists", m.id)
	}

	now := strconv.FormatInt(time.Now().Unix(), 10)
	embedding := float32ToBytes(stubEmbedding(m.content))
	fields := map[string]string{
		"id":           m.id,
		"user_id":      m.userID,
		"project_id":   "default",
		"memory_type":  m.memType,
		"content":      m.content,
		"source":       "demo",
		"embedding":    string(embedding),
		"created_at":   now,
		"updated_at":   now,
		"access_count": "0",
		"importance":   "0.5",
	}
	if _, err := client.HSet(ctx, key, fields); err != nil {
		return fmt.Errorf("HSET failed: %w", err)
	}
	return nil
}

// memResult is a parsed memory retrieval hit.
type memResult struct {
	id, content string
	score       float64
}

// retrieveMemory runs a user-scoped KNN search, the core of the router's
// Retrieve path (before hybrid reranking and thresholding).
func retrieveMemory(ctx context.Context, client *glide.Client, userID, query string, topK int) ([]memResult, error) {
	filterExpr := fmt.Sprintf("@user_id:{%s}", escapeTagValue(userID))
	knnQuery := fmt.Sprintf("(%s)=>[KNN %d @embedding $BLOB AS vector_distance]", filterExpr, topK)
	embedding := float32ToBytes(stubEmbedding(query))
	cmd := []string{
		"FT.SEARCH", memIndex, knnQuery,
		"PARAMS", "2", "BLOB", string(embedding),
		"RETURN", "3", "id", "content", "vector_distance",
		"LIMIT", "0", strconv.Itoa(topK),
		"DIALECT", "2",
	}
	result, err := client.CustomCommand(ctx, cmd)
	if err != nil {
		return nil, fmt.Errorf("FT.SEARCH failed: %w", err)
	}

	var results []memResult
	for _, fields := range parseSearchDocs(result) {
		distance, _ := strconv.ParseFloat(fmt.Sprint(fields["vector_distance"]), 64)
		results = append(results, memResult{
			id:      fmt.Sprint(fields["id"]),
			content: fmt.Sprint(fields["content"]),
			score:   cosineDistanceToSimilarity(distance),
		})
	}
	sort.Slice(results, func(i, j int) bool { return results[i].score > results[j].score })
	return results, nil
}

// recordAccess atomically increments access_count, the concurrency-safe access
// tracking the router uses (access_count lives only as a top-level HASH field,
// never in the metadata JSON, to avoid clobbering under concurrent reads).
func recordAccess(ctx context.Context, client *glide.Client, id string) (int64, error) {
	key := memPrefix + id
	count, err := client.HIncrBy(ctx, key, "access_count", 1)
	if err != nil {
		return 0, fmt.Errorf("HINCRBY failed: %w", err)
	}
	return count, nil
}

// forgetByUser deletes all memories for a user in pages, re-querying at offset
// 0 each round since each DEL shifts the remaining matches forward. This
// mirrors the router's ForgetByScope.
func forgetByUser(ctx context.Context, client *glide.Client, userID string) (int, error) {
	filterExpr := fmt.Sprintf("@user_id:{%s}", escapeTagValue(userID))
	const pageSize = 1000
	total := 0
	for {
		cmd := []string{
			"FT.SEARCH", memIndex, filterExpr,
			"RETURN", "1", "id",
			"LIMIT", "0", strconv.Itoa(pageSize),
			"DIALECT", "2",
		}
		result, err := client.CustomCommand(ctx, cmd)
		if err != nil {
			return total, fmt.Errorf("FT.SEARCH failed: %w", err)
		}
		keys := docKeys(result)
		if len(keys) == 0 {
			break
		}
		deleted, err := client.Del(ctx, keys)
		if err != nil {
			return total, fmt.Errorf("DEL failed: %w", err)
		}
		total += int(deleted)
	}
	return total, nil
}

// docKeys returns the document (hash) keys from an FT.SEARCH response. These are
// the actual Valkey keys, suitable for DEL.
func docKeys(result any) []string {
	arr, ok := result.([]interface{})
	if !ok || len(arr) < 2 {
		return nil
	}
	var keys []string
	for i := 1; i < len(arr); i++ {
		switch v := arr[i].(type) {
		case string:
			keys = append(keys, v)
		case map[string]interface{}:
			for k := range v {
				keys = append(keys, k)
			}
		}
	}
	return keys
}
