# Aiohttp Demo - Valkey GLIDE Async Client

Minimal aiohttp app demonstrating Valkey GLIDE async client patterns from `SKILL.md`.

## Setup

```bash
cd skill/aiohttp_demo
pip install -r requirements.txt
```

## Run

```bash
# Start Valkey (Docker)
docker run -d -p 6379:6379 valkey/valkey:latest

# Run aiohttp app (port 5001)
export VALKEY_URL=valkey://localhost:6379
python app.py
```

## Test Endpoints

### Health Check
```bash
curl http://localhost:5001/health
```

### Create Index
```bash
curl -X POST http://localhost:5001/index/create \
  -H "Content-Type: application/json" \
  -d '{"index_name": "docs_idx", "dimensions": 3}'
```

### Delete Index
```bash
curl -X DELETE http://localhost:5001/index/docs_idx
```

### Recreate Index (nuke and rebuild)
```bash
curl -X PUT http://localhost:5001/index/docs_idx \
  -H "Content-Type: application/json" \
  -d '{"dimensions": 3}'
```

### Add Document
```bash
curl -X POST http://localhost:5001/document \
  -H "Content-Type: application/json" \
  -d '{
    "id": "doc1",
    "embedding": [0.1, 0.2, 0.3],
    "category": "tech"
  }'
```

### Search
```bash
curl -X POST http://localhost:5001/search \
  -H "Content-Type: application/json" \
  -d '{
    "index_name": "docs_idx",
    "vector": [0.1, 0.2, 0.3],
    "k": 5
  }'
```

### Search with Filter
```bash
curl -X POST http://localhost:5001/search \
  -H "Content-Type: application/json" \
  -d '{
    "index_name": "docs_idx",
    "vector": [0.1, 0.2, 0.3],
    "k": 5,
    "filter": "@category:{tech}"
  }'
```

### Get Index Info
```bash
curl http://localhost:5001/index/info/docs_idx
```

## Run Tests

```bash
# In another terminal
python test_app.py
```

## Patterns Demonstrated

- ✅ Async client creation with cluster fallback
- ✅ URL parsing for connection strings
- ✅ Index creation with typed field objects
- ✅ Index deletion and recreation
- ✅ Vector search with KNN queries
- ✅ Metadata filtering
- ✅ Proper import organization with TYPE_CHECKING
- ✅ Error handling with helpful messages
- ✅ Bytes decoding for JSON serialization
- ✅ Async/await patterns throughout

## Differences from Flask Demo

- Uses `aiohttp` instead of Flask
- All operations are `async`/`await`
- Runs on port 5001 (Flask uses 5000)
- Uses `valkey-glide` (async) instead of `valkey-glide-sync`
- Demonstrates proper async client lifecycle
