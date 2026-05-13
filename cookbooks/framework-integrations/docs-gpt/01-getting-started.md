# Getting Started with DocsGPT + Valkey

**Beginner** · Python · ~15 min

## What is DocsGPT + Valkey?

[DocsGPT](https://github.com/arc53/DocsGPT) is an open-source AI assistant platform that lets you build intelligent agents with document retrieval (RAG). It supports pluggable vector store backends — FAISS, PostgreSQL, Elasticsearch, Qdrant, Milvus, and now **Valkey**.

Using Valkey as the vector store gives you:

* **Sub-millisecond vector search** — HNSW indexing with cosine similarity
* **Source isolation** — each document source gets its own filtered namespace
* **Simple deployment** — single Valkey instance handles both vector search and caching
* **No additional database** — if you already run Valkey for caching or sessions, reuse it for vectors

## Prerequisites

* Docker or Podman installed
* Python 3.10+
* Git

## Step 1: Start Valkey with Search Module

The simplest option is `valkey-bundle`, which includes the search module out of the box:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Alternatively, load the module explicitly with the base image:

```bash
docker run -d --name valkey \
  -p 6379:6379 \
  valkey/valkey:8.1 \
  --loadmodule /usr/lib/valkey/modules/valkeysearch.so
```

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should show "search" in the output
```

## Step 2: Clone and Configure DocsGPT

```bash
git clone https://github.com/arc53/DocsGPT.git
cd DocsGPT
```

Create your `.env` file:

```bash
cp .env-template .env
```

Edit `.env` and set:

```env
VECTOR_STORE=valkey
VALKEY_HOST=localhost
VALKEY_PORT=6379
```

## Step 3: Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r application/requirements.txt
```

This installs `valkey-glide-sync` which provides the synchronous GLIDE client for Valkey.

## Step 4: Verify the Connection

```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    addresses=[NodeAddress(host="localhost", port=6379)]
)
client = GlideClient.create(config)
print(client.ping())  # b'PONG'
```

## Step 5: Run DocsGPT

Start the backend:

```bash
flask --app application/app.py run --host=0.0.0.0 --port=7091
```

DocsGPT will automatically create the Valkey search index on first use. You can now ingest documents through the UI or API — they'll be stored as vector embeddings in Valkey.

> **Note**: This runs the development server. For production deployment with Docker Compose, see [02 - Production Deployment](02-ingestion-and-retrieval.md#step-5-production-deployment-with-docker-compose).

## How It Works Under the Hood

When you ingest a document, DocsGPT:

1. **Chunks** the document into passages
2. **Embeds** each chunk using the configured embedding model
3. **Stores** each chunk as a Valkey HASH with fields: `content`, `source_id`, `metadata`, `embedding`
4. **Indexes** the embeddings with an HNSW vector index via `FT.CREATE`

When you ask a question:

1. The query is embedded into a vector
2. `FT.SEARCH` performs KNN search filtered by `source_id`
3. Top-k results are returned as context for the LLM

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| Create index | `FT.CREATE docsgpt ON HASH PREFIX doc: SCHEMA ...` | One-time index setup |
| Store chunk | `HSET doc:{uuid} content "..." source_id "..." embedding <bytes>` | Store document with vector |
| Search | `FT.SEARCH docsgpt @source_id:{id} =>[KNN k @embedding $BLOB]` | Vector similarity search |
| Delete source | `FT.SEARCH` + `DEL` per key | Remove all chunks for a source |

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `VECTOR_STORE` | `faiss` | Set to `valkey` to use Valkey |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `VALKEY_PASSWORD` | (none) | Password for authentication |
| `VALKEY_USE_TLS` | `false` | Enable TLS connections |
| `VALKEY_INDEX_NAME` | `docsgpt` | Name of the search index |
| `VALKEY_PREFIX` | `doc:` | Key prefix for document hashes |

## What's Next

Now that Valkey is connected, the next cookbook dives into how ingestion and search work under the hood — chunking, embedding storage, HNSW indexing, and filtered KNN retrieval.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide_sync'` | Run `pip install valkey-glide-sync` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` or add `--loadmodule` flag |
| Empty search results | Verify `source_id` matches what was used during ingestion |
| `NOAUTH Authentication required` | Set `VALKEY_PASSWORD` in your `.env` file |

## Authentication Options

`valkey-glide` supports multiple authentication methods depending on your deployment:

| Method | Use Case | Documentation |
|--------|----------|---------------|
| **Username/Password (ACL)** | Self-managed Valkey with ACL users configured | [Authentication Guide](https://glide.valkey.io/how-to/security/authentication/) |
| **Password only (`requirepass`)** | Simple deployments with a single shared password | [Authentication Guide](https://glide.valkey.io/how-to/security/authentication/) |
| **TLS / mTLS** | Encrypt in-transit data; verify client identity with certificates | [TLS Guide](https://glide.valkey.io/how-to/security/tls/) |
| **AWS IAM** | Amazon ElastiCache / MemoryDB clusters (auto token rotation) | [IAM Integration](https://glide.valkey.io/how-to/security/iam-integration/) |

DocsGPT exposes `VALKEY_PASSWORD` and `VALKEY_USE_TLS` environment variables for basic auth and TLS. For advanced configurations (custom CA certs, IAM token rotation), you'll need to modify the `ValkeyStore` initialization to pass the appropriate `ServerCredentials` or `TlsAdvancedConfiguration` to the GLIDE client. See the linked guides above for connection examples.

[Next: 02 Document Ingestion & Retrieval →](02-ingestion-and-retrieval.md)
