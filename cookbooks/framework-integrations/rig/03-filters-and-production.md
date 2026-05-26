# Filters & Production

> Use RediSearch filter syntax for metadata filtering, combine filters with AND/OR/NOT, and configure `rig-redis` for production with connection management and TLS.

**Intermediate** · Rust · ~15 min

## Step 1: Metadata Filtering

`rig-redis` translates Rig's generic filter API into Valkey Search query syntax (compatible with RediSearch). Filters are applied *before* the KNN search, narrowing the candidate set:

```rust
use rig_redis::Filter;
use rig_redis::filter::RedisValue;
use rig_core::vector_store::request::{SearchFilter, VectorSearchRequest};

// Filter by tag field
let category_filter = Filter::eq("category", RedisValue::from("architecture"));

let results = store
    .top_n::<KnowledgeBase>( // KnowledgeBase type from Cookbook 02
        VectorSearchRequest::builder()
            .query("How does the system handle failures?")
            .samples(5)
            .filter(category_filter)
            .build(),
    )
    .await?;
```

The generated query: `@category:{architecture}=>[KNN 5 @embedding $vec AS __vector_score]`

## Step 2: Numeric Range Filters

For NUMERIC fields in your schema, use range filters:

```rust
// Exact numeric match
let price_filter = Filter::eq("price", RedisValue::from(99.99));
// @price:[99.99 99.99]

// Greater than
let expensive = Filter::gt("price", RedisValue::from(50.0));
// @price:[(50 +inf]

// Range (inclusive)
let mid_range = Filter::range("price", 25.0, 100.0);
// @price:[25 100]

// Greater than or equal
let recent = Filter::gte("year", RedisValue::from(2024.0));
// @year:[2024 +inf]
```

## Step 3: Combining Filters

Use `.and()`, `.or()`, and `.not()` to compose complex queries:

```rust
// Category is "ops" AND year >= 2024
let filter = Filter::eq("category", RedisValue::from("ops"))
    .and(Filter::gte("year", RedisValue::from(2024.0)));

// Category is "api" OR category is "architecture"
let filter = Filter::eq("category", RedisValue::from("api"))
    .or(Filter::eq("category", RedisValue::from("architecture")));

// Multiple tags at once (OR within a single field)
let filter = Filter::tag_in("tags", vec!["rust".into(), "valkey".into()]);
// @tags:{rust | valkey}

// Negation
let filter = Filter::eq("status", RedisValue::from("archived")).not();
// -@status:{archived}
```

## Step 4: Full-Text Search Within Fields

Combine vector similarity with text matching:

```rust
let filter = Filter::text_contains("document", "deployment");

let results = store
    .top_n::<KnowledgeBase>(
        VectorSearchRequest::builder()
            .query("production setup")
            .samples(5)
            .filter(filter)
            .build(),
    )
    .await?;
```

## Step 5: Index Schema for Filtering

Your index schema must declare filterable fields. Update the `FT.CREATE` command:

```bash
docker exec valkey valkey-cli FT.CREATE doc_idx \
  ON HASH \
  PREFIX 1 "doc:" \
  SCHEMA \
    document TEXT \
    embedded_text TEXT \
    category TAG \
    year NUMERIC \
    tags TAG SEPARATOR "," \
    embedding VECTOR FLAT 6 \
      TYPE FLOAT32 \
      DIM 1536 \
      DISTANCE_METRIC COSINE
```

| Field Type | Filter Operations | Example |
|-----------|-------------------|---------|
| `TAG` | eq, tag_in, not | `@category:{ops}` |
| `NUMERIC` | eq, gt, lt, gte, lte, range | `@year:[2024 +inf]` |
| `TEXT` | text_contains | `@document:deployment` |

## Step 6: Production Configuration

### Connection Manager

`rig-redis` uses a `ConnectionManager` internally — it automatically reconnects on transient failures. No extra configuration needed.

### TLS (ElastiCache for Valkey)

```rust
let client = redis::Client::open("rediss://my-cluster.cache.amazonaws.com:6379")?;
//                                 ^^^^^^ note: rediss:// (with double-s) enables TLS

let store = RedisVectorStore::new(
    model,
    client,
    "doc_idx".to_string(),
    "embedding".to_string(),
)
.await?
.with_key_prefix("doc:".to_string());
```

### Authentication

```rust
// With password (AUTH)
let client = redis::Client::open("rediss://:my-auth-token@my-cluster.cache.amazonaws.com:6379")?;
```

### HNSW vs FLAT Indexing

For production workloads with >100k vectors, use HNSW instead of FLAT:

```bash
docker exec valkey valkey-cli FT.CREATE doc_idx \
  ON HASH \
  PREFIX 1 "doc:" \
  SCHEMA \
    document TEXT \
    embedded_text TEXT \
    embedding VECTOR HNSW 6 \
      TYPE FLOAT32 \
      DIM 1536 \
      DISTANCE_METRIC COSINE
```

| Algorithm | Best For | Trade-off |
|-----------|----------|-----------|
| `FLAT` | <100k vectors, exact results | O(n) scan, perfect recall |
| `HNSW` | >100k vectors, production | ~O(log n), approximate but fast |

### Key Prefix Strategy

Match your prefix to the index's `PREFIX` configuration:

```rust
// Index created with: PREFIX 1 "prod:docs:"
let store = RedisVectorStore::new(model, client, "doc_idx".into(), "embedding".into())
    .await?
    .with_key_prefix("prod:docs:".to_string());
```

---

[← 02 - Vector Search](02-vector-search.md)
