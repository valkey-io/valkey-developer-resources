package main

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/constants"
	"github.com/valkey-io/valkey-glide/go/v2/options"
	"github.com/valkey-io/valkey-glide/go/v2/servermodules/glideft"
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

// runMemoryDemo mirrors the router's agentic memory backend (PR #1739):
// duplicate-prevented store (HSETNX), user-scoped vector retrieval, atomic
// access tracking (HINCRBY), and scoped deletion.
func runMemoryDemo(ctx context.Context, client *glide.Client) error {
	fmt.Println("== vLLM Semantic Router — Valkey agentic memory demo ==")

	// Idempotent cleanup from any prior run.
	_, _ = glideft.FtDropIndex(ctx, client, memIndex)
	deleteByPrefix(ctx, client, memPrefix)

	if err := createMemoryIndex(ctx, client); err != nil {
		return err
	}
	defer func() {
		_, _ = glideft.FtDropIndex(ctx, client, memIndex)
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

		// Atomic access tracking via HINCRBY, applied to the memory that was
		// actually retrieved above (not a hardcoded id), so the printed count
		// reflects the same memory the reader just saw returned.
		count, err := recordAccess(ctx, client, results[0].id)
		if err != nil {
			return err
		}
		fmt.Printf("✓ Access count incremented to %d after retrieval\n", count)
	} else {
		fmt.Println("  (no results)")
	}

	// User isolation: bob's query must never see alice's memories.
	bobResults, err := retrieveMemory(ctx, client, "bob", "what does the user prefer?", 5)
	if err != nil {
		return err
	}
	fmt.Printf("✓ User isolation: %q sees %d of alice's memories\n", "bob", len(bobResults))

	// Scoped deletion: remove everything for alice.
	deleted, err := forgetByUser(ctx, client, "alice")
	if err != nil {
		return err
	}
	fmt.Printf("✓ ForgetByScope deleted %d memories for %q\n", deleted, "alice")
	return nil
}

// createMemoryIndex builds the richer memory index with scoping and ranking
// fields. created_at is SORTABLE so List can page chronologically server-side.
func createMemoryIndex(ctx context.Context, client *glide.Client) error {
	schema := []options.Field{
		options.NewTagField("id"),
		options.NewTagField("user_id"),
		options.NewTagField("project_id"),
		options.NewTagField("memory_type"),
		options.NewTextField("content"),
		options.NewTagField("source"),
		options.NewVectorFieldHNSW("embedding", constants.DistanceMetricCosine, embedDim).
			SetNumberOfEdges(16).                  // HNSW M
			SetVectorsExaminedOnConstruction(256), // HNSW EF_CONSTRUCTION
		options.NewNumericField("created_at").SetSortable(true),
		options.NewNumericField("updated_at"),
		options.NewNumericField("access_count"),
		options.NewNumericField("importance"),
	}
	opts := &options.FtCreateOptions{
		DataType: constants.IndexDataTypeHash,
		Prefixes: []string{memPrefix},
	}
	if _, err := glideft.FtCreate(ctx, client, memIndex, schema, opts); err != nil {
		return fmt.Errorf("FT.CREATE failed (is the Search module loaded?): %w", err)
	}
	return nil
}

// storeMemory reserves the id with HSETNX then writes the fields with HSET.
// Note this is NOT a single atomic operation: HSETNX prevents a duplicate
// overwrite, but a concurrent reader between the two calls could observe a key
// with only the id field set. The router accepts this for duplicate-prevention;
// wrapping both in MULTI/EXEC would make it fully atomic if needed.
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
	// string(embedding) coerces raw FLOAT32 bytes into a binary-safe string for
	// the VECTOR field; see cache.go for the rationale.
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
	// A user-scoped retrieval requires a userID: an empty value would build the
	// TAG expression @user_id:{} which valkey-search silently matches to zero
	// documents. Reject it rather than return a confusing empty result.
	if userID == "" {
		return nil, fmt.Errorf("retrieveMemory requires a non-empty userID")
	}
	filterExpr := fmt.Sprintf("@user_id:{%s}", escapeTagValue(userID))
	knnQuery := fmt.Sprintf("(%s)=>[KNN %d @embedding $BLOB AS vector_distance]", filterExpr, topK)
	embedding := float32ToBytes(stubEmbedding(query))
	dialect := 2
	searchOpts := &options.FtSearchOptions{
		Params: []options.FtSearchParam{{Key: "BLOB", Value: string(embedding)}},
		ReturnFields: []options.FtSearchReturnField{
			{FieldIdentifier: "id"},
			{FieldIdentifier: "content"},
			{FieldIdentifier: "vector_distance"},
		},
		Limit:   &options.FtSearchLimit{Offset: 0, Count: topK},
		Dialect: &dialect,
	}
	result, err := glideft.FtSearch(ctx, client, memIndex, knnQuery, searchOpts)
	if err != nil {
		return nil, fmt.Errorf("FT.SEARCH failed: %w", err)
	}

	var results []memResult
	for _, doc := range result.Documents {
		fields := doc.Fields
		// A parse failure here must not be discarded: cosineDistanceToSimilarity(0)
		// == 1.0, so silently defaulting distance to 0 would report a false
		// perfect match instead of surfacing that the field was missing or
		// malformed.
		distance, err := strconv.ParseFloat(fmt.Sprint(fields["vector_distance"]), 64)
		if err != nil {
			return nil, fmt.Errorf("vector_distance field missing or non-numeric: %w", err)
		}
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
	if userID == "" {
		return 0, fmt.Errorf("forgetByUser requires a non-empty userID")
	}
	filterExpr := fmt.Sprintf("@user_id:{%s}", escapeTagValue(userID))
	const pageSize = 1000
	// maxRounds caps the paging loop so a pathological condition (keys being
	// recreated concurrently, or a DEL that cannot remove them) can never spin
	// forever. pageSize*maxRounds bounds the total deletions per call.
	const maxRounds = 1000
	dialect := 2
	total := 0
	for round := 0; round < maxRounds; round++ {
		searchOpts := &options.FtSearchOptions{
			ReturnFields: []options.FtSearchReturnField{{FieldIdentifier: "id"}},
			Limit:        &options.FtSearchLimit{Offset: 0, Count: pageSize},
			Dialect:      &dialect,
		}
		result, err := glideft.FtSearch(ctx, client, memIndex, filterExpr, searchOpts)
		if err != nil {
			return total, fmt.Errorf("FT.SEARCH failed: %w", err)
		}
		if len(result.Documents) == 0 {
			break
		}
		// The typed result exposes each document's hash key directly, so the
		// keys are ready for DEL without a second response parser.
		keys := make([]string, 0, len(result.Documents))
		for _, doc := range result.Documents {
			keys = append(keys, doc.Key)
		}
		deleted, err := client.Del(ctx, keys)
		if err != nil {
			return total, fmt.Errorf("DEL failed: %w", err)
		}
		total += int(deleted)
	}
	return total, nil
}
