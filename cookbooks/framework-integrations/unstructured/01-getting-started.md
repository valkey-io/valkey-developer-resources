# Getting Started with Unstructured + Valkey

> Install the Valkey destination connector, start a local Valkey instance,
> and verify end-to-end connectivity.

**Beginner** · Python · ~10 min

**Who is this for:** Python developers building document ingestion pipelines
who want to store chunked, embedded documents in Valkey for semantic search.

## Prerequisites

- Python 3.11+
- Docker or Podman installed
- No paid API keys required

## Step 1: Start Valkey

```bash
docker run -d --name valkey \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

The `valkey-bundle` image includes the Search module needed for vector
indexes.

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify the server is running and the Search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your
> container runtime — the commands are identical.

## Step 2: Install Dependencies

> ⚠️ **Not yet released:** The `unstructured-ingest[valkey]` extra depends on
> [Unstructured-IO/unstructured-ingest#747](https://github.com/Unstructured-IO/unstructured-ingest/pull/747)
> which is not yet merged. Until it ships, use `valkey-glide` directly as
> shown in the [sample scripts](sample/scripts/). The API patterns are
> identical — the connector wraps valkey-glide internally.

Once released, install with:

```bash
pip install 'unstructured-ingest[valkey]'
```

This will install the Valkey connector with
[valkey-glide](https://github.com/valkey-io/valkey-glide) (async) and
`valkey-glide-sync` (sync) clients.

For document processing you also need:

```bash
pip install 'unstructured[all-docs]'
```

Or install everything from the sample's pinned requirements:

```bash
pip install -r sample/requirements.txt
```

## Step 3: Understand the Data Model

The Unstructured pipeline transforms documents through these stages:

```text
Source → Partition → Chunk → Embed → Upload (Valkey)
```

The Valkey destination connector handles the **Upload** step. Each document
chunk becomes a Valkey hash:

```text
Key: doc:unstructured:{element_id}

Fields:
  text             → chunk text content
  element_type     → "NarrativeText", "Title", "ListItem", etc.
  source_document  → original filename
  page_number      → source page number
  record_id        → file identifier (for incremental re-ingestion)
  metadata_json    → full metadata as JSON
  embedding        → float32 vector (binary blob)
```

A Valkey Search index with an HNSW vector field enables KNN queries across
all stored chunks.

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
    ssl=False,
    access_config=ValkeyAccessConfig(
        # password="your-password",  # Uncomment for auth
    ),
)

upload_config = ValkeyUploaderConfig(
    batch_size=50,
    key_prefix="doc:unstructured:",
    index_name="documents_index",
    distance_metric="COSINE",
    # ttl_seconds=86400,  # Optional: auto-expire after 24h
)

uploader = ValkeyUploader(
    connection_config=connection_config,
    upload_config=upload_config,
)
```

## Step 5: Verify Connectivity

```python
uploader.precheck()
print("Connected to Valkey!")
```

The `precheck()` method pings the server and verifies connectivity. It raises
`DestinationConnectionError` with a clear message if anything is wrong:

```python
from unstructured_ingest.error import DestinationConnectionError

try:
    uploader.precheck()
    print("✓ Connected to Valkey")
except DestinationConnectionError as e:
    print(f"✗ Connection failed: {e}")
```

## How It Works

| Component | Role |
| ----------- | ------ |
| `unstructured-ingest` | ETL pipeline: partition, chunk, embed documents |
| `ValkeyConnectionConfig` | Connection parameters (host, port, TLS, auth) |
| `ValkeyUploaderConfig` | Upload behavior (batch size, key prefix, index name) |
| `ValkeyUploader` | Orchestrates batch writes and index creation |
| Valkey Search | HNSW vector index for KNN similarity queries |

## Configuration Reference

### Connection Options

| Parameter | Required | Default | Description |
| ----------- | ---------- | --------- | ------------- |
| `host` | ✓* | — | Valkey hostname or IP |
| `port` | — | `6379` | Valkey port |
| `ssl` | — | `True` | Use TLS for the connection |
| `username` | — | — | ACL username |
| `password` | — | — | Authentication password |
| `uri` | ✓* | — | Full URI (alternative to host/port) |
| `request_timeout` | — | `30000` | Request timeout in milliseconds |

*Either `host` or `uri` must be provided.

URI examples: `valkey://host:6379` or `valkeys://host:6379` (TLS).

### Upload Options

| Parameter | Required | Default | Description |
| ----------- | ---------- | --------- | ------------- |
| `batch_size` | — | `100` | Elements per batch write |
| `key_prefix` | — | `doc:unstructured:` | Key prefix for stored hashes |
| `index_name` | — | `unstructured_index` | FT Search index name |
| `ttl_seconds` | — | — | Auto-expire keys after N seconds |
| `distance_metric` | — | `COSINE` | Vector distance: COSINE, L2, or IP |

## Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| `DestinationConnectionError` | Valkey not running or wrong host/port | Verify with `valkey-cli PING` |
| "Search module not loaded" | Using plain `valkey` image | Switch to `valkey/valkey-bundle:9.1.0` |
| "Index already exists" | Re-running after prior upload | Expected — connector skips creation |
| Timeout on large batches | HNSW indexing blocks batch response | Reduce `batch_size` or use incremental mode |

## Next Steps

You've connected the Unstructured pipeline to Valkey. Next, run a full
document ingestion pipeline with embedding and KNN search.

---

[02 - Document Ingestion & Search →](02-ingestion-and-search.md)
