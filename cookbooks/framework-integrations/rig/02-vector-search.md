# Vector Search with Rig + Valkey

> Insert documents with embeddings, run KNN queries with `top_n` and `top_n_ids`, apply score thresholds, and wire vector search into a Rig RAG agent.

**Intermediate** · Rust · ~20 min

This cookbook builds on [Getting Started](01-getting-started.md). You'll learn the full document lifecycle — batch insertion, different query modes, threshold filtering, and integrating vector search into a Rig agent for RAG.

## Step 1: Batch Document Insertion

`rig-redis` uses Valkey pipelines internally for efficient batch writes. Each document gets a UUID key with your configured prefix:

```rust
use anyhow::Result;
use rig_core::{Embed, embeddings::EmbeddingsBuilder, embeddings::embedding::EmbeddingModel, vector_store::InsertDocuments};
use rig_redis::RedisVectorStore;
use serde::{Deserialize, Serialize};

#[derive(Embed, Serialize, Deserialize, Clone, Debug)]
struct KnowledgeBase {
    source: String,
    #[embed]
    text: String,
    category: String,
}

async fn ingest(store: &RedisVectorStore<impl EmbeddingModel>, model: impl EmbeddingModel) -> Result<()> {
    let docs = vec![
        KnowledgeBase {
            source: "docs/architecture.md".into(),
            text: "The system uses event sourcing with Valkey streams for durability.".into(),
            category: "architecture".into(),
        },
        KnowledgeBase {
            source: "docs/deployment.md".into(),
            text: "Deploy with 3 replicas behind an ALB. Use ElastiCache for Valkey in production.".into(),
            category: "ops".into(),
        },
        KnowledgeBase {
            source: "docs/api.md".into(),
            text: "The /search endpoint accepts a JSON body with query and top_k fields.".into(),
            category: "api".into(),
        },
    ];

    let embeddings = EmbeddingsBuilder::new(model)
        .documents(docs)?
        .build()
        .await?;

    store.insert_documents(embeddings).await?;
    Ok(())
}
```

Under the hood, each document is stored as:

```
HSET doc:{uuid}
  document   '{"source":"docs/architecture.md","text":"...","category":"architecture"}'
  embedded_text "The system uses event sourcing..."
  embedding  <f32 bytes>
```

## Step 2: Query with top_n

`top_n` returns full deserialized documents with similarity scores:

```rust
use rig_core::vector_store::{VectorStoreIndex, request::VectorSearchRequest};

let results = store
    .top_n::<KnowledgeBase>(
        VectorSearchRequest::builder()
            .query("How do I deploy the system?")
            .samples(3)
            .build(),
    )
    .await?;

for (score, id, doc) in &results {
    println!("[{score:.4}] {id} — {} ({})", doc.source, doc.category);
}
// [0.9102] doc:abc — docs/deployment.md (ops)
// [0.7654] doc:def — docs/architecture.md (architecture)
// [0.6012] doc:ghi — docs/api.md (api)
```

## Step 3: Query with top_n_ids

When you only need IDs and scores (e.g., for a two-phase retrieval), use `top_n_ids` — it skips deserializing the document field:

```rust
let id_results = store
    .top_n_ids(
        VectorSearchRequest::builder()
            .query("event sourcing")
            .samples(5)
            .build(),
    )
    .await?;

for (score, id) in &id_results {
    println!("[{score:.4}] {id}");
}
```

## Step 4: Score Thresholds

Filter out low-confidence results with `.threshold()`:

```rust
let results = store
    .top_n::<KnowledgeBase>(
        VectorSearchRequest::builder()
            .query("How does authentication work?")
            .samples(10)
            .threshold(0.75)
            .build(),
    )
    .await?;

// Only results with similarity >= 0.75 are returned.
// If nothing meets the threshold, you get an empty vec.
```

This is useful for RAG — you can detect "I don't know" cases when no documents pass the threshold.

## Step 5: RAG with a Rig Agent

Wire vector search into a Rig agent to answer questions from your knowledge base:

```rust
use anyhow::Result;
use rig_core::client::{CompletionClient, EmbeddingsClient, ProviderClient};
use rig_core::providers::openai;
use rig_core::agent::AgentBuilder;
use rig_redis::RedisVectorStore;

#[tokio::main]
async fn main() -> Result<()> {
    let openai = openai::Client::from_env()?;
    let embedding_model = openai.embedding_model(openai::TEXT_EMBEDDING_3_SMALL);
    let chat_model = openai.completion_model(openai::GPT_4O);

    let client = redis::Client::open("redis://127.0.0.1:6379")?;

    let store = RedisVectorStore::new(
        embedding_model.clone(),
        client,
        "doc_idx".to_string(),
        "embedding".to_string(),
    )
    .await?
    .with_key_prefix("doc:".to_string());

    // Build a RAG agent with vector search as context
    let agent = AgentBuilder::new(chat_model)
        .preamble("Answer questions using the provided context. If the context doesn't contain relevant information, say so.")
        .dynamic_context(2, store)
        .build();

    let response = agent
        .prompt("How should I deploy the system?")
        .await?;

    println!("{response}");
    Ok(())
}
```

The agent automatically:
1. Embeds the user's question
2. Runs a KNN search against Valkey
3. Injects the top 2 results as context
4. Generates a grounded answer

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Filters & Production →](03-filters-and-production.md)
