# CocoIndex + Valkey Sample

> Build an incremental Markdown indexing pipeline with CocoIndex and search
> the resulting HNSW index in Valkey.

## Prerequisites

- Python 3.11 or newer
- Docker or Podman with Compose support
- Network access to PyPI and the public sentence-transformers model on the
  first install and run

The sample uses SQLite for CocoIndex state and a local sentence-transformers
model. It does not require a cloud account, API key, GPU, or external
database.

## Setup

Run these commands from the repository root:

```bash
cd cookbooks/framework-integrations/cocoindex/sample
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e ".[test]"
```

Start the pinned Valkey Bundle service and wait for its health check:

```bash
docker compose up -d --wait
```

Build the index from the Markdown fixtures:

```bash
.venv/bin/cocoindex update --reset -f main
```

Run a semantic query and a TAG-filtered query:

```bash
.venv/bin/python main.py "open source in-memory database"
```

Run the integration test:

```bash
.venv/bin/python -m pytest -q
```

The query prints matching fixture filenames and scores. The test fails if
Valkey is unreachable, the Search module is unavailable, the index is missing,
or no fixture matches the query.

## Configuration Reference

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `localhost` | Valkey hostname |
| `VALKEY_PORT` | `6379` | Valkey port |
| `COCOINDEX_DB` | `./cocoindex.db` | SQLite state path used by CocoIndex |
| `COCOINDEX_INDEX_NAME` | `rag_documents` | Valkey Search index name |
| `COCOINDEX_EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Public local embedding model |

Copy `.env.example` to `.env` to override these values. The first embedding
run downloads the model into the local Hugging Face cache.

## Security

The local Compose service has no authentication or TLS. Keep it bound to
localhost for development. For any non-local deployment, configure Valkey ACL
credentials and TLS in `valkey.create_client_config`; do not put credentials in
source files or committed `.env` files.

## Cleanup

The integration test removes the `rag_documents` index and its
`rag_documents:*` document keys. Remove the local service and SQLite state when
finished:

```bash
docker compose down -v
rm -rf cocoindex.db
```
