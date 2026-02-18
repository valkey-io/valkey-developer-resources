# Flask Demo - Valkey GLIDE Sync Client

Minimal Flask app demonstrating Valkey GLIDE sync client patterns from `SKILL.md`.

## Setup

```bash
cd skill/flask_demo
pip install -r requirements.txt
```

## Run

```bash
# Start Valkey (Docker)
docker run -d -p 6379:6379 valkey/valkey:latest

# Run Flask app
export VALKEY_URL=valkey://localhost:6379
python app.py
```

## Test Endpoints

### Health Check
```bash
curl http://localhost:5000/health
```

### Create Index
```bash
curl -X POST http://localhost:5000/index/create \
  -H "Content-Type: application/json" \
  -d '{"index_name": "docs_idx", "dimensions": 3}'
```

### Add Document
```bash
curl -X POST http://localhost:5000/document \
  -H "Content-Type: application/json" \
  -d '{
    "id": "doc1",
    "embedding": [0.1, 0.2, 0.3],
    "category": "tech"
  }'
```

### Search
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{
    "index_name": "docs_idx",
    "vector": [0.1, 0.2, 0.3],
    "k": 5
  }'
```

### Search with Filter
```bash
curl -X POST http://localhost:5000/search \
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
curl http://localhost:5000/index/info/docs_idx
```

## Patterns Demonstrated

- ✅ Sync client creation with cluster fallback
- ✅ URL parsing for connection strings
- ✅ Index creation with typed field objects
- ✅ Vector search with KNN queries
- ✅ Metadata filtering
- ✅ Proper import organization with TYPE_CHECKING
- ✅ Error handling with helpful messages
