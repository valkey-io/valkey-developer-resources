# GPTCache + Valkey Sample

Validates GPTCache's `RedisVectorStore` patterns against Valkey. This sample exercises the
exact commands GPTCache uses — `FT.CREATE`, `FT.SEARCH` with KNN, `HSET`, and `INFO SERVER`
— using the valkey-py client.

## Quick Start

### 1. Start Valkey

```bash
docker compose up -d
```

### 2. Install dependencies

With uv:

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[test]"
```

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
```

### 3. Run tests

```bash
pytest -v
```

## What's tested

- Connectivity and backend detection (`INFO SERVER`)
- Search module availability (`FT._LIST`)
- Vector index creation (`FT.CREATE` with FLAT FLOAT32 COSINE)
- Document storage and retrieval (`HSET` / `HGETALL`)
- KNN vector search with distance scoring
- SORTBY behavior (not supported in Valkey Search)
- Namespace isolation via key prefixes
