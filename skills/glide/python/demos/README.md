# Valkey GLIDE Code Snippets

Reusable code snippets extracted from working implementations.

## Synchronous Client Snippets

### Client Creation
- **File:** `client_creation_sync.py`
- **Functions:** `get_client()`, `_parse_valkey_url()`
- **Usage:** Create GLIDE sync client with automatic cluster detection

### Index Management
- **File:** `index_management_sync.py`
- **Functions:** `create_vector_index()`, `index_exists()`, `drop_index()`
- **Usage:** Create and manage vector search indexes

### Vector Search
- **File:** `vector_search_sync.py`
- **Functions:** `vector_search()`, `add_document()`
- **Usage:** Perform KNN similarity search and add documents

## Asynchronous Client Snippets

### Client Creation
- **File:** `client_creation_async.py`
- **Functions:** `get_client()`, `_parse_valkey_url()`
- **Usage:** Create GLIDE async client with automatic cluster detection

### Vector Search
- **File:** `vector_search_async.py`
- **Functions:** `vector_search()`, `add_document()`
- **Usage:** Perform async KNN similarity search and add documents

## Usage

Copy the relevant snippet into your project and import:

```python
# Sync
from your_module.snippets.client_creation_sync import get_client
from your_module.snippets.vector_search_sync import vector_search

# Async
from your_module.snippets.client_creation_async import get_client
from your_module.snippets.vector_search_async import vector_search
```

## Key Patterns Demonstrated

- ✅ TYPE_CHECKING for conditional imports
- ✅ Helpful ImportError messages
- ✅ Cluster fallback logic
- ✅ URL parsing for connection strings
- ✅ Typed field objects for schema
- ✅ KNN query construction
- ✅ Metadata filtering
- ✅ Vector byte conversion with struct.pack
- ✅ Result parsing from ft.search
