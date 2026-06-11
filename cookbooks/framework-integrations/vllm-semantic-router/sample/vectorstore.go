package main

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"time"

	glide "github.com/valkey-io/valkey-glide/go/v2"
)

// vsPrefix is the collection prefix the router's vector store backend uses to
// namespace index and key names (default "vsr_vs_").
const vsPrefix = "vsr_vs_"

// chunk is a document chunk to embed and store, mirroring the router's
// EmbeddedChunk type.
type chunk struct {
	id, fileID, filename, content string
	chunkIndex                    int
}

var sampleChunks = []chunk{
	{"c1", "f1", "france.txt", "The capital of France is Paris, known for the Eiffel Tower.", 0},
	{"c2", "f1", "france.txt", "France is a country in Western Europe with a rich cultural heritage.", 1},
	{"c3", "f2", "germany.txt", "Berlin is the capital of Germany, famous for the Brandenburg Gate.", 0},
	{"c4", "f2", "germany.txt", "Germany is the largest economy in Europe and a leader in engineering.", 1},
	{"c5", "f3", "japan.txt", "Tokyo is the capital of Japan, one of the most populous cities on earth.", 0},
}

// searchResult is a parsed vector-store hit.
type searchResult struct {
	fileID, filename, content string
	chunkIndex                int
	score                     float64
}

// runVectorStoreDemo mirrors the router's vector store backend (PR #1671):
// create a per-collection HNSW index, insert chunks, run KNN search, and run a
// search scoped to a single file_id.
func runVectorStoreDemo(ctx context.Context, client *glide.Client) error {
	fmt.Println("== vLLM Semantic Router — Valkey vector store demo ==")

	const collection = "demo"
	idxName := vsPrefix + collection + "_idx"

	// Idempotent cleanup of any stale collection from a prior run.
	deleteCollection(ctx, client, collection)

	if err := createCollection(ctx, client, collection, embedDim); err != nil {
		return err
	}
	defer func() {
		deleteCollection(ctx, client, collection)
		fmt.Printf("✓ Deleted collection %q\n", collection)
	}()
	fmt.Printf("✓ Created collection %q (dimension=%d)\n", collection, embedDim)

	if err := insertChunks(ctx, client, collection, sampleChunks); err != nil {
		return err
	}
	fmt.Printf("✓ Inserted %d chunks\n", len(sampleChunks))

	time.Sleep(500 * time.Millisecond) // allow async indexing to settle

	for _, q := range []string{"capital of France", "German engineering"} {
		fmt.Printf("→ Query: %q\n", q)
		results, err := vectorSearch(ctx, client, idxName, q, 3, 0.0, "")
		if err != nil {
			return err
		}
		printResults(results)
	}

	fmt.Println("→ Filtered query (file_id=f2 only): \"capital city\"")
	filtered, err := vectorSearch(ctx, client, idxName, "capital city", 5, 0.0, "f2")
	if err != nil {
		return err
	}
	printResults(filtered)
	return nil
}

func createCollection(ctx context.Context, client *glide.Client, collection string, dimension int) error {
	idxName := vsPrefix + collection + "_idx"
	prefix := vsPrefix + collection + ":"
	cmd := []string{
		"FT.CREATE", idxName,
		"ON", "HASH",
		"PREFIX", "1", prefix,
		"SCHEMA",
		"id", "TAG",
		"file_id", "TAG",
		"filename", "TAG",
		"content", "TEXT",
		"chunk_index", "NUMERIC",
		"created_at", "NUMERIC",
		"embedding", "VECTOR", "HNSW", "10",
		"TYPE", "FLOAT32",
		"DIM", strconv.Itoa(dimension),
		"DISTANCE_METRIC", "COSINE",
		"M", "16",
		"EF_CONSTRUCTION", "200",
	}
	if _, err := client.CustomCommand(ctx, cmd); err != nil {
		return fmt.Errorf("FT.CREATE failed (is the Search module loaded?): %w", err)
	}
	return nil
}

// deleteCollection drops the index and sweeps the collection's keys with SCAN +
// DEL (never KEYS), matching the router's DeleteCollection cleanup.
func deleteCollection(ctx context.Context, client *glide.Client, collection string) {
	idxName := vsPrefix + collection + "_idx"
	_, _ = client.CustomCommand(ctx, []string{"FT.DROPINDEX", idxName})
	deleteByPrefix(ctx, client, vsPrefix+collection+":")
}

func insertChunks(ctx context.Context, client *glide.Client, collection string, chunks []chunk) error {
	now := strconv.FormatInt(time.Now().Unix(), 10)
	for _, c := range chunks {
		key := vsPrefix + collection + ":" + c.id
		embedding := float32ToBytes(stubEmbedding(c.content))
		cmd := []string{
			"HSET", key,
			"id", c.id,
			"file_id", c.fileID,
			"filename", c.filename,
			"content", c.content,
			"chunk_index", strconv.Itoa(c.chunkIndex),
			"created_at", now,
			"embedding", string(embedding),
		}
		if _, err := client.CustomCommand(ctx, cmd); err != nil {
			return fmt.Errorf("HSET chunk %s failed: %w", c.id, err)
		}
	}
	return nil
}

// vectorSearch runs a KNN query, optionally scoped to a file_id TAG filter, and
// returns results sorted best-first above the threshold.
func vectorSearch(ctx context.Context, client *glide.Client, idxName, query string, topK int, threshold float64, fileID string) ([]searchResult, error) {
	filterExpr := "*"
	if fileID != "" {
		filterExpr = fmt.Sprintf("@file_id:{%s}", escapeTagValue(fileID))
	}
	knnQuery := fmt.Sprintf("(%s)=>[KNN %d @embedding $BLOB AS vector_distance]", filterExpr, topK)
	embedding := float32ToBytes(stubEmbedding(query))
	cmd := []string{
		"FT.SEARCH", idxName, knnQuery,
		"PARAMS", "2", "BLOB", string(embedding),
		"RETURN", "5", "file_id", "filename", "content", "chunk_index", "vector_distance",
		"LIMIT", "0", strconv.Itoa(topK),
		"DIALECT", "2",
	}
	result, err := client.CustomCommand(ctx, cmd)
	if err != nil {
		return nil, fmt.Errorf("FT.SEARCH failed: %w", err)
	}

	var results []searchResult
	for _, fields := range parseSearchDocs(result) {
		distance, _ := strconv.ParseFloat(fmt.Sprint(fields["vector_distance"]), 64)
		score := cosineDistanceToSimilarity(distance)
		if score < threshold {
			continue
		}
		idx, _ := strconv.Atoi(fmt.Sprint(fields["chunk_index"]))
		results = append(results, searchResult{
			fileID:     fmt.Sprint(fields["file_id"]),
			filename:   fmt.Sprint(fields["filename"]),
			content:    fmt.Sprint(fields["content"]),
			chunkIndex: idx,
			score:      score,
		})
	}
	// Go map iteration loses FT.SEARCH's ordering, so re-sort best-first.
	sort.Slice(results, func(i, j int) bool { return results[i].score > results[j].score })
	return results, nil
}

func printResults(results []searchResult) {
	if len(results) == 0 {
		fmt.Println("  (no results)")
		return
	}
	for rank, r := range results {
		fmt.Printf("  #%d [%.2f] %s: %s\n", rank+1, r.score, r.filename, truncate(r.content, 60))
	}
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max-3] + "..."
}
