# Getting Started with Eino + Valkey

> Connect Eino to Valkey, index documents with embeddings, and run your first vector similarity search using the valkey-glide Go client.

**Beginner** · Go · ~15 min

[Eino](https://github.com/cloudwego/eino) is a Go framework for building AI applications from CloudWeGo. The [eino-ext](https://github.com/cloudwego/eino-ext) repository provides Valkey components that implement Eino's `Indexer` and `Retriever` interfaces, enabling vector similarity search backed by Valkey Search.

## Prerequisites

- Docker installed (or a running Valkey 9.1+ instance with the Search module)
- Go 1.22+
- CGO enabled (the valkey-glide Go client requires the Rust core library)

## Step 1: Start Valkey

Vector search requires the `valkey-bundle` image, which includes the Search module:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable `requirepass` and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# should include: name search
```

## Step 2: Create the Search Index

Before indexing documents, create a vector search index. Connect with the CLI and run:

```bash
docker exec valkey valkey-cli FT.CREATE my_index ON HASH PREFIX 1 doc: SCHEMA \
  content TEXT \
  vector_content VECTOR HNSW 6 TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE
```

This creates an index named `my_index` that:
- Watches Hash keys prefixed with `doc:`
- Indexes a `content` text field (for hybrid search)
- Indexes a `vector_content` field as an HNSW vector with 1536 dimensions (matching OpenAI `text-embedding-3-small`)

> **Tip:** Adjust `DIM` to match your embedding model's output dimensions.
>
> **Note:** The `sample/` directory in this cookbook uses `DIM 4` with a mock embedder for quick testing without an API key. If running the sample, use `DIM 4` in your `FT.CREATE` command instead.

## Step 3: Initialize the Project

```bash
mkdir eino-valkey-demo && cd eino-valkey-demo
go mod init eino-valkey-demo
go get github.com/cloudwego/eino-ext/components/indexer/valkey@latest
go get github.com/cloudwego/eino-ext/components/retriever/valkey@latest
go get github.com/valkey-io/valkey-glide/go/v2@latest
```

## Step 4: Index Documents

Create `main.go`:

```go
package main

import (
	"context"
	"fmt"
	"log"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/cloudwego/eino/schema"

	valkeyIndexer "github.com/cloudwego/eino-ext/components/indexer/valkey"
)

func main() {
	ctx := context.Background()

	// 1. Create Valkey GLIDE client
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379})
	client, err := glide.NewClient(cfg)
	if err != nil {
		log.Fatalf("failed to create client: %v", err)
	}
	defer client.Close()

	// 2. Create the indexer
	indexer, err := valkeyIndexer.NewIndexer(ctx, &valkeyIndexer.IndexerConfig{
		Client:    client,
		KeyPrefix: "doc:",
		BatchSize: 10,
		Embedding: yourEmbedder(), // see note below
	})
	if err != nil {
		log.Fatalf("failed to create indexer: %v", err)
	}

	// 3. Store documents — embeddings are generated automatically
	docs := []*schema.Document{
		{ID: "1", Content: "Valkey is a high-performance in-memory data store forked from Redis."},
		{ID: "2", Content: "Vector search enables finding semantically similar documents."},
		{ID: "3", Content: "Eino is a Go framework for building AI applications."},
	}

	ids, err := indexer.Store(ctx, docs)
	if err != nil {
		log.Fatalf("store error: %v", err)
	}
	fmt.Printf("Stored %d documents: %v\n", len(ids), ids)
}
```

> **Embedding:** The indexer requires an `embedding.Embedder` implementation. Eino-ext provides OpenAI, Bedrock, and other embedders in `components/embedding/`. For example:
> ```go
> import openaiEmb "github.com/cloudwego/eino-ext/components/embedding/openai"
>
> func yourEmbedder(ctx context.Context) (*openaiEmb.Embedder, error) {
>     emb, err := openaiEmb.NewEmbedder(ctx, &openaiEmb.EmbeddingConfig{
>         Model: "text-embedding-3-small", // 1536 dims
>     })
>     if err != nil {
>         return nil, err
>     }
>     return emb, nil
> }
> ```

## Step 5: Retrieve Documents

Create a separate file `retrieve/main.go` (or replace `main.go`):

```go
package main

import (
	"context"
	"fmt"
	"log"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"

	valkeyRetriever "github.com/cloudwego/eino-ext/components/retriever/valkey"
)

func main() {
	ctx := context.Background()

	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379})
	client, err := glide.NewClient(cfg)
	if err != nil {
		log.Fatalf("failed to create client: %v", err)
	}
	defer client.Close()

	// Create retriever
	retriever, err := valkeyRetriever.NewRetriever(ctx, &valkeyRetriever.RetrieverConfig{
		Client:      client,
		Index:       "my_index",
		VectorField: "vector_content",
		TopK:        3,
		Embedding:   yourEmbedder(),
	})
	if err != nil {
		log.Fatalf("failed to create retriever: %v", err)
	}

	// Search by semantic similarity
	docs, err := retriever.Retrieve(ctx, "What is Valkey?")
	if err != nil {
		log.Fatalf("retrieve error: %v", err)
	}

	for _, doc := range docs {
		fmt.Printf("ID: %s | %s\n", doc.ID, doc.Content)
	}
}
```

Expected output:

```
ID: doc:1 | Valkey is a high-performance in-memory data store forked from Redis.
ID: doc:2 | Vector search enables finding semantically similar documents.
ID: doc:3 | Eino is a Go framework for building AI applications.
```

## Step 6: Filtered Search

The retriever supports hybrid queries with filter expressions:

```go
docs, err := retriever.Retrieve(ctx, "data store",
    valkeyRetriever.WithFilterQuery("@content:Valkey"))
```

This combines vector similarity with a text filter — only documents whose `content` field contains "Valkey" are considered.

## How It Works

| Component | Role |
|-----------|------|
| `valkeyIndexer.Indexer` | Embeds documents via your `Embedder`, stores them as Valkey Hashes with `HSET` using pipeline batching |
| `valkeyRetriever.Retriever` | Embeds the query, runs `FT.SEARCH` with KNN against the index, returns ranked documents |
| Valkey Search | Maintains the HNSW vector index, executes similarity queries server-side |
| valkey-glide | Go client providing the connection and command layer |

The indexer uses pipeline batch execution (`Exec`) for high throughput — documents are written in a single round-trip regardless of batch size.

## Configuration Reference

### IndexerConfig

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `Client` | ✓ | — | Valkey GLIDE client |
| `KeyPrefix` | — | `""` | Prefix for document keys (must match index `PREFIX`) |
| `DocumentType` | — | `Hash` | `DocumentTypeHash` or `DocumentTypeJSON` |
| `BatchSize` | — | `10` | Texts per embedding batch call |
| `Embedding` | ✓ | — | Embedder for vectorizing content |
| `DocumentToHashes` | — | built-in | Custom Hash field mapping |
| `DocumentToJSON` | — | built-in | Custom JSON field mapping |

### RetrieverConfig

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `Client` | ✓ | — | Valkey GLIDE client |
| `Index` | ✓ | — | Search index name |
| `VectorField` | — | `"vector_content"` | Vector field in the index schema |
| `TopK` | — | `5` | Number of results |
| `Embedding` | ✓ | — | Embedder for vectorizing queries |
| `DistanceThreshold` | — | `nil` | Set for range search (requires Valkey Search 2.0+) |
| `Dialect` | — | `2` | Query dialect version |
| `ReturnFields` | — | `["content", "vector_content"]` | Fields returned from search |

---

[02 - RAG Pipeline →](02-rag-pipeline.md)
