# Quick Start Guide

## For AI Agents

When implementing Valkey operations, follow these patterns from `SKILL.md`:

### 1. Choose Sync or Async
- **Sync** (`valkey-glide-sync`) - Flask, Django, LangChain, sync frameworks
- **Async** (`valkey-glide-async`) - FastAPI, aiohttp, async frameworks

### 2. Client Creation
```python
# Sync
from snippets.client_creation_sync import get_client
client = get_client("valkey://localhost:6379")

# Async
from snippets.client_creation_async import get_client
client = await get_client("valkey://localhost:6379")
```

### 3. Vector Search
```python
# Sync
from snippets.vector_search_sync import vector_search
results = vector_search(client, "docs_idx", [0.1, 0.2, 0.3], k=5)

# Async
from snippets.vector_search_async import vector_search
results = await vector_search(client, "docs_idx", [0.1, 0.2, 0.3], k=5)
```

### 4. Index Management
```python
# Sync only (async version similar)
from snippets.index_management_sync import create_vector_index

create_vector_index(
    client,
    "docs_idx",
    dimensions=1536,
    metadata_fields={"category": "tag", "year": "numeric"}
)
```

## For Developers

### Try the Flask Demo
```bash
# Start Valkey
docker run -d -p 6379:6379 valkey/valkey:latest

# Run demo
cd skill/flask_demo
pip install -r requirements.txt
python app.py

# Test it
python test_app.py
```

### Use the Snippets
Copy from `skill/snippets/` into your project and import:

```python
from your_module.snippets.client_creation_sync import get_client
from your_module.snippets.vector_search_sync import vector_search, add_document
```

## Key Constraints

1. ✅ Use `valkey-glide-sync` or `valkey-glide-async`
2. ❌ Never use `valkey` package (Redis fork)
3. ✅ Use `ft.search(client, ...)` not `client.ft.search(...)`
4. ✅ Wrap params in `FtSearchOptions(params={...})`
5. ❌ Don't add `.sort_by()` to KNN queries (already sorted)

## Resources

- **Full Skill**: [SKILL.md](SKILL.md)
- **Flask Demo**: [flask_demo/](flask_demo/)
- **Code Snippets**: [snippets/](snippets/)
- **Validation**: [VALIDATION.md](VALIDATION.md)
