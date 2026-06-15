# RAG Pipeline with Eino + Valkey

> Build a retrieval-augmented generation pipeline using Eino's orchestration with Valkey as the vector store.

**Intermediate** · Go · ~20 min

This cookbook builds on [01 - Getting Started](01-getting-started.md). You'll wire the Valkey retriever into an Eino workflow that retrieves relevant documents, formats a prompt with context, and generates an answer via an LLM.

## Prerequisites

- Completed [Getting Started](01-getting-started.md) (Valkey running, index created, documents indexed)
- An OpenAI API key (or substitute any Eino-compatible model/embedder)

## Step 1: Install Additional Dependencies

```bash
go get github.com/cloudwego/eino/compose@latest
go get github.com/cloudwego/eino/components/prompt@latest
go get github.com/cloudwego/eino-ext/components/model/openai@latest
go get github.com/cloudwego/eino-ext/components/embedding/openai@latest
```

## Step 2: Define the RAG Workflow

The pipeline has three stages:
1. **Retrieve** — embed the query and find relevant documents in Valkey
2. **Format** — inject retrieved context into a prompt template
3. **Generate** — send the prompt to an LLM for an answer

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"

	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/schema"

	openaiEmb "github.com/cloudwego/eino-ext/components/embedding/openai"
	openaiModel "github.com/cloudwego/eino-ext/components/model/openai"
	valkeyRetriever "github.com/cloudwego/eino-ext/components/retriever/valkey"
)

func main() {
	ctx := context.Background()

	// --- Valkey client ---
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379})
	client, err := glide.NewClient(cfg)
	if err != nil {
		log.Fatalf("failed to create client: %v", err)
	}
	defer client.Close()

	// --- Embedder ---
	emb, err := openaiEmb.NewEmbedder(ctx, &openaiEmb.EmbeddingConfig{
		Model:  "text-embedding-3-small",
		APIKey: os.Getenv("OPENAI_API_KEY"),
	})
	if err != nil {
		log.Fatalf("failed to create embedder: %v", err)
	}

	// --- Retriever ---
	ret, err := valkeyRetriever.NewRetriever(ctx, &valkeyRetriever.RetrieverConfig{
		Client:      client,
		Index:       "my_index",
		VectorField: "vector_content",
		TopK:        3,
		Embedding:   emb,
	})
	if err != nil {
		log.Fatalf("failed to create retriever: %v", err)
	}

	// --- Chat Model ---
	chatModel, err := openaiModel.NewChatModel(ctx, &openaiModel.ChatModelConfig{
		Model:  "gpt-4o-mini",
		APIKey: os.Getenv("OPENAI_API_KEY"),
	})
	if err != nil {
		log.Fatalf("failed to create chat model: %v", err)
	}

	// --- Build the RAG workflow ---
	type Input struct {
		Query string
	}
	type Output struct {
		Answer string
	}

	wf := compose.NewWorkflow[Input, Output]()

	// Node 1: Retrieve documents from Valkey
	wf.AddRetrieverNode("retrieve", ret).
		AddInput(compose.START, compose.FromField("Query"))

	// Node 2: Format context + question into a prompt
	formatFn := func(ctx context.Context, docs []*schema.Document) ([]*schema.Message, error) {
		var contextParts []string
		for _, doc := range docs {
			contextParts = append(contextParts, doc.Content)
		}
		context := strings.Join(contextParts, "\n---\n")

		return []*schema.Message{
			schema.SystemMessage(fmt.Sprintf(
				"Answer the user's question based only on the following context.\n\nContext:\n%s",
				context,
			)),
		}, nil
	}
	wf.AddLambdaNode("format", compose.InvokableLambda(formatFn)).
		AddInput("retrieve")

	// We need the original query for the user message — use a passthrough
	wf.AddPassthroughNode("query_pass").
		AddInput(compose.START, compose.FromField("Query"))

	// Node 3: Combine system message (from format) with user query, then call LLM
	combineFn := func(ctx context.Context, in struct {
		System []*schema.Message
		Query  string
	}) ([]*schema.Message, error) {
		messages := append(in.System, schema.UserMessage(in.Query))
		return messages, nil
	}
	wf.AddLambdaNode("combine", compose.InvokableLambda(combineFn)).
		AddInput("format", compose.ToField("System")).
		AddInput("query_pass", compose.ToField("Query"))

	// Node 4: Generate answer
	wf.AddChatModelNode("generate", chatModel).
		AddInput("combine")

	// Extract answer from model response
	extractFn := func(ctx context.Context, msg *schema.Message) (Output, error) {
		return Output{Answer: msg.Content}, nil
	}
	wf.AddLambdaNode("extract", compose.InvokableLambda(extractFn)).
		AddInput("generate")

	wf.End().AddInput("extract")

	// --- Compile and run ---
	runner, err := wf.Compile(ctx)
	if err != nil {
		log.Fatalf("failed to compile workflow: %v", err)
	}

	result, err := runner.Invoke(ctx, Input{Query: "What is Valkey?"})
	if err != nil {
		log.Fatalf("invoke error: %v", err)
	}

	fmt.Println(result.Answer)
}
```

## How the Workflow Executes

```
START ──┬── retrieve ── format ──┐
        │                        ├── combine ── generate ── extract ── END
        └── query_pass ──────────┘
```

1. `retrieve` receives the query string, embeds it, runs `FT.SEARCH` against Valkey, returns `[]*schema.Document`
2. `format` converts retrieved documents into a system message with context
3. `query_pass` forwards the original query unchanged
4. `combine` merges the system message and user query into a `[]*schema.Message`
5. `generate` calls the LLM
6. `extract` pulls the answer text from the response

## Step 3: Run It

```bash
export OPENAI_API_KEY="sk-..."
go run main.go
```

Expected output (varies by LLM):

```
Valkey is a high-performance in-memory data store that was forked from Redis.
It supports vector search for finding semantically similar documents.
```

## Streaming Responses

Replace `Invoke` with `Stream` to get token-by-token output:

```go
stream, err := runner.Stream(ctx, Input{Query: "What is Valkey?"})
if err != nil {
    log.Fatalf("stream error: %v", err)
}

for chunk := range stream.Recv() {
    if chunk.Err != nil {
        log.Fatalf("stream chunk error: %v", chunk.Err)
    }
    fmt.Print(chunk.Value.Answer)
}
fmt.Println()
```

> **Note:** Streaming requires the chat model node to support it. The OpenAI model component streams by default.

## Adding Filters

Restrict retrieval to a subset of documents by adding a filter expression:

```go
// Instead of the plain retriever, wrap it with filter options
docs, err := ret.Retrieve(ctx, query,
    valkeyRetriever.WithFilterQuery("@category:{technology}"))
```

To use filters inside the workflow, wrap the retriever in a lambda that applies the filter:

```go
filteredRetrieve := func(ctx context.Context, query string) ([]*schema.Document, error) {
    return ret.Retrieve(ctx, query,
        valkeyRetriever.WithFilterQuery("@category:{technology}"))
}

wf.AddLambdaNode("retrieve", compose.InvokableLambda(filteredRetrieve)).
    AddInput(compose.START, compose.FromField("Query"))
```

## Next Steps

- **Add document ingestion** — use the Valkey indexer in a separate workflow to load and embed documents from files
- **Hybrid search** — combine vector similarity with full-text search using filter expressions
- **Observability** — add Eino callbacks (LangFuse, LangSmith) to trace retrieval and generation latency
- **Production** — configure timeouts, TLS, and reconnection strategy on the GLIDE client

---

[← 01 - Getting Started](01-getting-started.md)
