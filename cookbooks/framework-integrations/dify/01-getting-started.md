# Getting Started with Dify and Valkey

> Configure Dify to use Valkey as its vector database for knowledge base embeddings, enabling fast similarity search powered by the valkey-search module.

**Beginner** · Python · ~20 min

**Who is this for:** Developers self-hosting Dify who want a lightweight, high-performance vector store without deploying a separate vector database like Qdrant or Weaviate.

## Prerequisites

- Docker and Docker Compose
- A running Dify instance (or willingness to deploy one)
- Basic familiarity with Dify's knowledge base feature

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey with the Search Module

Dify's vector store requires the `valkey-search` module for `FT.CREATE` and `FT.SEARCH` commands. Use the `valkey-bundle` image which includes it:

```bash
docker run -d --name valkey-vector \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:latest
```

Verify the search module is loaded:

```bash
docker exec valkey-vector valkey-cli MODULE LIST
# Should show "search" in the output
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Configure Dify Environment

Add Valkey vector store settings to your Dify environment. If using Dify's Docker Compose deployment, create or edit the `valkey.env` file:

```bash
# docker/envs/vectorstores/valkey.env
VECTOR_STORE=valkey
VALKEY_HOST=valkey-vector
VALKEY_PORT=6379
VALKEY_PASSWORD=
VALKEY_DB=0
VALKEY_USE_SSL=false
VALKEY_DISTANCE_METRIC=COSINE
```

Add the Valkey service to your `docker-compose.yaml`:

```yaml
services:
  valkey-vector:
    image: valkey/valkey-bundle:latest
    restart: always
    volumes:
      - ./volumes/valkey:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

## Step 3: Understand the Data Model

When you create a knowledge base in Dify and upload documents, the Valkey backend:

1. **Creates an FT index** per collection with HNSW vector indexing:

    ```text
    FT.CREATE idx:{collection_name}
      ON HASH PREFIX 1 doc:{collection_name}:
      SCHEMA
        vector VECTOR HNSW 6 TYPE FLOAT32 DIM {auto} DISTANCE_METRIC COSINE
        group_id TAG
        doc_id TAG
        document_id TAG
        page_content TEXT
    ```

2. **Stores each chunk** as a HASH key:

    ```text
    HSET doc:{collection_name}:{chunk_id}
      vector <float32_bytes>
      page_content "The actual text content..."
      metadata '{"source": "file.pdf", "page": 3}'
      group_id {dataset_id}
      doc_id {chunk_id}
      document_id {file_id}
    ```

3. **Searches via KNN** when you query the knowledge base:

    ```text
    FT.SEARCH idx:{collection_name}
      "(@group_id:{dataset_id})=>[KNN 4 @vector $query_vector]"
      PARAMS 2 query_vector <float32_bytes>
      LIMIT 0 4
    ```

## Step 4: Verify the Integration

After uploading a document to a Dify knowledge base configured with Valkey:

1. Check that the index was created:

    ```bash
    docker exec valkey-vector valkey-cli FT._LIST
    # Should show your index name, e.g., "idx:abc123def"
    ```

2. Check stored documents:

    ```bash
    docker exec valkey-vector valkey-cli KEYS "doc:*" | head -5
    ```

3. Inspect a document hash:

    ```bash
    docker exec valkey-vector valkey-cli HGETALL "doc:abc123def:chunk_001"
    ```

## Step 5: Test Vector Search Directly

You can query the vector index directly using `valkey-cli` for debugging:

```bash
# Count indexed documents
docker exec valkey-vector valkey-cli FT.INFO "idx:abc123def" | grep num_docs

# Full-text search (keyword match on page_content)
docker exec valkey-vector valkey-cli FT.SEARCH "idx:abc123def" "@page_content:valkey"
```

## How It Works

### Distance Metrics

Dify's Valkey backend supports three distance metrics, configurable via `VALKEY_DISTANCE_METRIC`:

| Metric | Description | Similarity formula | Range |
| --- | --- | --- | --- |
| `COSINE` | Cosine distance | `1 - distance/2` | [0, 1] |
| `L2` | Euclidean distance | `1 / (1 + distance)` | (0, 1] |
| `IP` | Inner product | `1 - distance` | varies |

### Distributed Locking

Index creation uses a distributed lock via Dify's internal Redis client (`ext_redis`) to prevent race conditions when multiple workers start simultaneously:

```python
lock_name = f"vector_indexing_lock_{collection_name}"
with redis_client.lock(lock_name, timeout=20):
    if not index_exists():
        create_index(vector_size)
```

This is the same pattern used by other Dify vector backends (e.g., Qdrant).

### Auto-detected Dimensions

Vector dimensions are not configured manually — they are detected from the first embedding passed to the store.
This means the index is created lazily on the first document upload, not at knowledge base creation time.

## Configuration Reference

| Environment Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `VECTOR_STORE` | `string` | — | Set to `valkey` to enable the Valkey backend |
| `VALKEY_HOST` | `string` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `int` | `6379` | Valkey server port |
| `VALKEY_PASSWORD` | `string` | `""` | Password for Valkey authentication |
| `VALKEY_DB` | `int` | `0` | Valkey database number |
| `VALKEY_USE_SSL` | `bool` | `false` | Enable TLS for the connection |
| `VALKEY_DISTANCE_METRIC` | `string` | `COSINE` | Distance metric: `COSINE`, `L2`, or `IP` |

## Troubleshooting

### "Module search is not loaded"

The Valkey instance doesn't have the `valkey-search` module. Ensure you're using `valkey/valkey-bundle` (not plain `valkey/valkey`):

```bash
docker exec valkey-vector valkey-cli MODULE LIST
```

If empty, switch to the bundle image.

### Index not created after uploading documents

Check Dify's worker logs for errors. The index is created lazily on the first embedding, so it won't exist until a document is processed:

```bash
docker logs dify-worker-1 2>&1 | grep -i valkey
```

### Connection refused

Ensure the Valkey container is on the same Docker network as Dify's API/worker containers, and that `VALKEY_HOST` matches the container/service name.

### Score threshold filtering out results

If queries return empty results despite matching documents, check the `score_threshold` parameter.
With `COSINE` distance, scores range from 0 to 1. A threshold of 0.5 means only results with ≥50% similarity are returned.

---

**Back to** [README](./README.md)
