# OpenAI + Valkey Cookbook Sample

> Run the Valkey Search path locally without credentials, then opt into OpenAI embeddings with one environment variable.

Runnable code for the [OpenAI + Valkey cookbook series](../README.md).

## Prerequisites

- Python 3.10 or newer
- Docker Compose or Podman Compose
- No external service for the default deterministic embedding path
- An OpenAI API key only when `OPENAI_API_KEY` is set

## Setup

Run these commands from this directory. Replace `docker compose` with
`podman compose` when using Podman:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The Compose file publishes Valkey only on `127.0.0.1` and uses the pinned
`valkey/valkey-bundle:9.1.0` image. The default path uses deterministic local
vectors. Set `OPENAI_API_KEY` in a local, untracked `.env` file to use OpenAI's
`text-embedding-3-small` model instead; OpenAI requests have a 10-second
timeout and one retry.

## Running

```bash
.venv/bin/python getting_started.py
.venv/bin/python vector_search.py
```

Both scripts assert their main behavior, are safe to run repeatedly, and remove their indexes and sample keys in `finally` blocks.

## Sample Scripts

| Script | Cookbook | Description |
| --- | --- | --- |
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Connect, create a FLAT JSON vector index, store documents, and run a KNN search |
| `vector_search.py` | [02 - Vector Search](../02-vector-search.md) | Create an HNSW index and combine a TAG pre-filter with KNN |

## Tests

```bash
.venv/bin/python -m pytest -q
```

The tests verify:

- KNN retrieval returns document content
- TAG-filtered search does not return another genre
- `VALKEY_HOST` and `VALKEY_PORT` overrides are read when a client is created
- a second run is idempotent
- cleanup removes sample data after an intentional failure

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | unset | Enables OpenAI embeddings; unset uses deterministic local vectors |
| `EMBED_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `OPENAI_EMBEDDING_DIM` | `1536` | Embedding dimension sent to OpenAI and used by the Valkey index |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

## Troubleshooting

- **Missing dependency**: Run `.venv/bin/python -m pip install -r requirements.txt`.
- **Connection refused**: Ensure Valkey is running on `localhost:6379` (`docker ps`).
- **Unknown command `FT.CREATE`**: Use `valkey/valkey-bundle:9.1.0`; it includes the Search module.
- **Authentication error from OpenAI**: Set `OPENAI_API_KEY` in `.env`.
- **Empty search results**: Verify `OPENAI_EMBEDDING_DIM` matches the active embedding model's output dimension.

## Optional OpenAI Setup

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY without committing the file.
.venv/bin/python getting_started.py
```

Do not use ambient credentials in automated tests. The default test path intentionally does not contact OpenAI.

## Teardown

The scripts remove their own indexes and keys. Stop the container when
finished. Replace `docker compose` with `podman compose` when using Podman:

```bash
docker compose down
```
