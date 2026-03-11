# Python GLIDE Anti-Patterns

This document contains additional anti-patterns specific to Python GLIDE development. **Critical constraints (package selection, binary data handling, vector search) are documented in `python.md`.**

---

## Testing Patterns

### ❌ INCORRECT: Mocking at definition location
```python
# ❌ WRONG: Mocking at glide_sync module
@patch("glide_sync.GlideClient")  # Won't work if already imported elsewhere
```

### ✅ CORRECT: Mock at import location
```python
# ✅ CORRECT: Mock at the import location
@patch("langchain_aws.utilities.valkey.GlideClient")
@patch("langchain_aws.utilities.valkey.GlideClusterClient")
def test_something(mock_cluster, mock_client):
    # Mock the create() class method
    mock_client.create.return_value = MagicMock()
    ...
```

**Why:** Mock at the location where the object is used, not where it's defined.

---

## Performance Optimization

### ❌ INCORRECT: Fetching entire JSON object
```python
# ❌ Inefficient — must fetch/parse entire object
user = json.loads(await client.get("user:123"))
name = user["name"]
```

### ✅ CORRECT: Use JSON.GET with path
```python
# ✅ Efficient — fetch only needed fields
name = await client.json_get("user:123", "$.name")
```

**Why:** Fetching only needed fields reduces network transfer and parsing overhead.

---

## Code Patterns

### ❌ INCORRECT: Exceptions as Control Flow
```python
async def fetch_data(key: str) -> str:
    value = await client.get(key)
    if value is None:
        raise ValueError("Not found")  # Don't use exceptions for normal logic
    return value
```

### ✅ CORRECT: Status-Based Returns
```python
async def fetch_data(key: str) -> dict:
    value = await client.get(key)
    if value is None:
        return {"status": "error", "msg": "Not found"}
    return {"status": "ok", "data": value}
```

**Why:** Exceptions are expensive and make code hard to read. Use status returns for predictable logic.

---

### ❌ INCORRECT: Static Method-Only Classes
```python
class CacheUtils:
    @staticmethod
    async def get_user(client, user_id: str) -> str:
        return await client.get(f"user:{user_id}")
```

### ✅ CORRECT: Module-Level Functions
```python
async def get_user(client, user_id: str) -> str:
    return await client.get(f"user:{user_id}")
```

**Why:** Python has modules for namespacing. Static-only classes add unnecessary boilerplate.

---

### ❌ INCORRECT: Tight Coupling
```python
class UserService:
    def __init__(self, host: str, port: int):
        self.config = GlideClientConfiguration([NodeAddress(host, port)])
        self.client = await GlideClient.create(self.config)
```

### ✅ CORRECT: Protocol-Based Abstraction
```python
from typing import Protocol

class CacheClient(Protocol):
    async def get(self, key: str) -> str: ...
    async def set(self, key: str, value: str): ...

class UserService:
    def __init__(self, cache: CacheClient):
        self.cache = cache
```

**Why:** Tight coupling makes testing difficult and prevents swapping implementations.

---

### ❌ INCORRECT: Wildcard Imports
```python
from glide import *  # Namespace pollution
```

### ✅ CORRECT: Explicit Imports
```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress
```

**Why:** Wildcard imports pollute namespace, cause name collisions, and break static analysis.

---
