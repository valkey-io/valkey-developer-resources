# Getting Started with Unstructured + Valkey

**Beginner** · Python · ~10 min

## What is Unstructured + Valkey?

Unstructured is an ETL framework that transforms raw documents (PDFs, HTML, Word, email) into structured, AI-ready data. Valkey stores the output as vector embeddings with HNSW indexes for semantic search.

Together they give you an end-to-end pipeline: documents in, searchable vectors out.

  * **Any document format** — PDF, DOCX, HTML, Markdown, email, images
  * **Automatic chunking** — splits documents into semantic chunks with metadata
  * **Vector embeddings** — each chunk stored with its embedding for similarity search
  * **Sub-millisecond KNN** — Valkey Search HNSW returns nearest neighbors in <1ms

## Step 1: Start Valkey

Docker installed and Python 3.11+ required.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes the Search module needed for vector indexes. Verify:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should show "search" module
```

## Step 2: Install Dependencies

```bash
pip install 'unstructured-ingest[valkey]'
```

This installs the Valkey connector with `valkey-glide` (async) and `valkey-glide-sync` (sync) clients.

For document processing you'll also need:

```bash
pip install 'unstructured[all-docs]'
```

## Step 3: Understand the Architecture

The Unstructured pipeline flows like this:

```
Source → Partition → Chunk → Embed → Upload (Valkey)
```

Our Valkey connector handles the Upload step. Each document chunk becomes a Valkey hash:

```
Key: doc:unstructured:{element_id}

Fields:
  text          → chunk text content
  element_type  → "NarrativeText", "Title", "ListItem", etc.
  source_document → original filename
  page_number   → source page
  embedding     → float32 vector (binary)
```

A Valkey Search index with an HNSW vector field enables KNN queries across all stored chunks.

## Step 4: Configure the Connector

```python
from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig,
    ValkeyConnectionConfig,
    ValkeyUploader,
    ValkeyUploaderConfig,
)

connection_config = ValkeyConnectionConfig(
    host="localhost",
    port=6379,
    ssl=False,  # Set True for cloud (ElastiCache, MemoryDB)
    access_config=ValkeyAccessConfig(
        # password="your-password",  # Uncomment for auth
    ),
)

upload_config = ValkeyUploaderConfig(
    batch_size=50,                    # Elements per batch write
    key_prefix="doc:unstructured:",   # Key prefix for all stored hashes
    index_name="documents_index",     # FT Search index name
    # ttl_seconds=86400,             # Optional: auto-expire after 24h
)

uploader = ValkeyUploader(
    connection_config=connection_config,
    upload_config=upload_config,
)

# Verify connection
uploader.precheck()
print("Connected to Valkey!")
```

## Step 5: Verify Connection with a Precheck

```python
uploader.precheck()
# If this doesn't raise, you're connected and ready to ingest.
```

The `precheck()` method pings the server and verifies connectivity. It raises `DestinationConnectionError` with a clear message if anything is wrong.

## Connection Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `host` | Valkey hostname | None |
| `port` | Valkey port | 6379 |
| `ssl` | Use TLS | True |
| `username` | ACL username | None |
| `password` | Auth password | None |
| `uri` | Full URI (alternative to host/port) | None |
| `request_timeout` | Timeout in ms | 30000 |

URI example: `valkey://user:pass@host:6379` or `valkeys://host:6379` (TLS).

[Next: 02 Document Ingestion Pipeline →](02-ingestion-and-search.md)
