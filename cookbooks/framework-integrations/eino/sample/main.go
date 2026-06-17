// Package main demonstrates Eino + Valkey vector indexing and retrieval.
//
// This sample uses a deterministic mock embedder so it can run without an API key.
// Replace mockEmbedder with a real embedding implementation (e.g., eino-ext openai embedder)
// for production use. See the cookbook for real-embedder examples.
//
// Prerequisites:
//   - Valkey 9.1+ with Search module:
//     docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
//   - Create the index:
//     docker exec valkey valkey-cli FT.CREATE my_index ON HASH PREFIX 1 doc: SCHEMA \
//       content TEXT vector_content VECTOR HNSW 6 TYPE FLOAT32 DIM 4 DISTANCE_METRIC COSINE
//
// Run: CGO_ENABLED=1 go run .
package main

import (
	"context"
	"fmt"
	"hash/fnv"
	"log"
	"math"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"

	"github.com/cloudwego/eino/components/embedding"
	"github.com/cloudwego/eino/schema"

	valkeyIndexer "github.com/cloudwego/eino-ext/components/indexer/valkey"
	valkeyRetriever "github.com/cloudwego/eino-ext/components/retriever/valkey"
)

func main() {
	ctx := context.Background()

	// --- Valkey client ---
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379})
	client, err := glide.NewClient(cfg)
	if err != nil {
		log.Fatalf("failed to create Valkey client: %v", err)
	}
	defer client.Close()

	// --- Embedder (mock — replace with real embedder for meaningful results) ---
	emb := &mockEmbedder{dims: 4}

	// --- Index documents ---
	indexer, err := valkeyIndexer.NewIndexer(ctx, &valkeyIndexer.IndexerConfig{
		Client:    client,
		KeyPrefix: "doc:",
		BatchSize: 10,
		Embedding: emb,
	})
	if err != nil {
		log.Fatalf("failed to create indexer: %v", err)
	}

	docs := []*schema.Document{
		{ID: "1", Content: "Valkey is a high-performance in-memory data store forked from Redis."},
		{ID: "2", Content: "Vector search enables finding semantically similar documents."},
		{ID: "3", Content: "Eino is a Go framework for building AI applications by CloudWeGo."},
	}

	ids, err := indexer.Store(ctx, docs)
	if err != nil {
		log.Fatalf("failed to store documents: %v", err)
	}
	fmt.Printf("✓ Indexed %d documents: %v\n\n", len(ids), ids)

	// --- Retrieve documents ---
	retriever, err := valkeyRetriever.NewRetriever(ctx, &valkeyRetriever.RetrieverConfig{
		Client:      client,
		Index:       "my_index",
		VectorField: "vector_content",
		TopK:        3,
		// Note: "distance" is not listed in ReturnFields — the retriever
		// automatically maps the KNN score to doc.MetaData["distance"].
		ReturnFields: []string{"content"},
		Embedding:    emb,
	})
	if err != nil {
		log.Fatalf("failed to create retriever: %v", err)
	}

	query := "What is Valkey?"
	fmt.Printf("Query: %q\n", query)
	fmt.Println("---")

	results, err := retriever.Retrieve(ctx, query)
	if err != nil {
		log.Fatalf("failed to retrieve: %v", err)
	}

	if len(results) == 0 {
		fmt.Println("  No results found.")
		return
	}

	for _, doc := range results {
		dist := doc.MetaData["distance"]
		fmt.Printf("  ID: %s | Distance: %v | %s\n", doc.ID, dist, doc.Content)
	}
}

// Compile-time interface check.
var _ embedding.Embedder = (*mockEmbedder)(nil)

// mockEmbedder produces deterministic hash-based vectors for testing.
// It demonstrates the Embedder interface contract. Replace with a real
// embedding model for semantic search quality.
type mockEmbedder struct {
	dims int
}

func (m *mockEmbedder) EmbedStrings(_ context.Context, texts []string, _ ...embedding.Option) ([][]float64, error) {
	vectors := make([][]float64, len(texts))
	for i, text := range texts {
		vectors[i] = hashVector(text, m.dims)
	}
	return vectors, nil
}

func hashVector(text string, dims int) []float64 {
	vec := make([]float64, dims)
	for i := range dims {
		h := fnv.New64a()
		h.Write([]byte(text))
		h.Write([]byte{byte(i)})
		bits := h.Sum64()
		vec[i] = float64(bits)/float64(math.MaxUint64)*2 - 1 // normalize to [-1, 1]
	}
	return vec
}
