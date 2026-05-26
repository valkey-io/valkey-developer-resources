# Getting Started with Rig + Valkey

> Use the `rig-redis` vector store crate to connect a Rig agent to Valkey for high-performance KNN vector similarity search.

**Beginner** · Rust · ~15 min

[Rig](https://github.com/0xPlaygrounds/rig) is a Rust framework for building modular, scalable LLM applications. The `rig-redis` crate adds a vector store backend that uses Valkey's `FT.SEARCH` command with KNN queries for sub-millisecond similarity search.

The `rig-redis` crate uses standard Redis protocol commands, which Valkey fully implements. This gives you native Valkey performance — including Valkey Search (`FT.*` commands) — with the existing Rig ecosystem.

## What You'll Build

A Rust application that:
1. Connects to Valkey
2. Creates a vector search index
3. Inserts documents with embeddings
4. Queries for similar documents using KNN

## Prerequisites

- Docker installed
- Rust 1.75+ with Cargo
- An OpenAI API key (or any Rig-supported embedding provider)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes the Search module required for `FT.SEARCH`. Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Create a New Project

```bash
cargo new rig-valkey-demo && cd rig-valkey-demo
```

Add dependencies to `Cargo.toml`:

```toml
[dependencies]
rig-core = { version = "0.37", features = ["derive"] }
rig-redis = "0.1"
redis = { version = "1.2", features = ["tokio-comp", "connection-manager"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
anyhow = "1"
```

## Step 3: Create the Vector Index

Before inserting documents, create a RediSearch index. Run this with `valkey-cli`:

```bash
docker exec valkey valkey-cli FT.CREATE doc_idx \
  ON HASH \
  PREFIX 1 "doc:" \
  SCHEMA \
    document TEXT \
    embedded_text TEXT \
    embedding VECTOR FLAT 6 \
      TYPE FLOAT32 \
      DIM 1536 \
      DISTANCE_METRIC COSINE
```

| Parameter | Value | Why |
|-----------|-------|-----|
| `PREFIX` | `doc:` | Only index keys starting with `doc:` |
| `DIM` | `1536` | Matches OpenAI `text-embedding-3-small` output |
| `DISTANCE_METRIC` | `COSINE` | Standard for text embeddings |

## Step 4: Connect and Search

```rust
use anyhow::Result;
use rig_core::{
    Embed,
    client::{EmbeddingsClient, ProviderClient},
    providers::openai,
    vector_store::{VectorStoreIndex, InsertDocuments},
    embeddings::EmbeddingsBuilder,
    vector_store::request::VectorSearchRequest,
};
use rig_redis::RedisVectorStore;
use serde::{Deserialize, Serialize};

#[derive(Embed, Serialize, Deserialize, Clone, Debug)]
struct Document {
    title: String,
    #[embed]
    content: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    // 1. Set up embedding model
    let openai = openai::Client::from_env()?;
    let model = openai.embedding_model(openai::TEXT_EMBEDDING_3_SMALL);

    // 2. Connect to Valkey
    let client = redis::Client::open("redis://127.0.0.1:6379")?;

    // 3. Create vector store
    let store = RedisVectorStore::new(
        model.clone(),
        client,
        "doc_idx".to_string(),
        "embedding".to_string(),
    )
    .await?
    .with_key_prefix("doc:".to_string());

    // 4. Insert documents
    let docs = vec![
        Document {
            title: "Valkey".to_string(),
            content: "Valkey is a high-performance key-value store with vector search.".to_string(),
        },
        Document {
            title: "Rig".to_string(),
            content: "Rig is a Rust framework for building LLM applications.".to_string(),
        },
    ];

    let embeddings = EmbeddingsBuilder::new(model.clone())
        .documents(docs)?
        .build()
        .await?;

    store.insert_documents(embeddings).await?;

    // 5. Search
    let results = store
        .top_n::<Document>(
            VectorSearchRequest::builder()
                .query("What is Valkey?")
                .samples(2)
                .build(),
        )
        .await?;

    for (score, id, doc) in &results {
        println!("[{score:.4}] {id} — {}", doc.title);
    }

    Ok(())
}
```

Run it:

```bash
OPENAI_API_KEY=sk-... cargo run
# [0.9234] doc:abc123 — Valkey
# [0.7891] doc:def456 — Rig
```

## How It Works Under the Hood

| Operation | Valkey Command | Description |
|-----------|---------------|-------------|
| Store document | `HSET doc:{uuid} document "..." embedded_text "..." embedding <bytes>` | Stores JSON doc + embedding as a hash |
| Search | `FT.SEARCH doc_idx "(*)=>[KNN 2 @embedding $vec ...]" PARAMS 2 vec <bytes>` | KNN query against the vector field |
| Score conversion | `1.0 - cosine_distance` | Converts distance (0=identical) to similarity (1=identical) |

---

[02 - Vector Search →](02-vector-search.md)
