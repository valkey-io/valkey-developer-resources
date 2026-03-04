# Python GLIDE Anti-Pattern Demonstrations

This demo proves common Python anti-patterns and their correct alternatives, based on [10 Python anti-patterns ruining your code](https://medium.com/@BuildShift/10-python-anti-patterns-ruining-your-code-and-what-to-do-instead-e304c457bc98).

## Running the Demo

```bash
cd python
source .venv/bin/activate
pip install valkey-glide
python3 anti_patterns_demo.py
```

## Anti-Patterns Demonstrated

### 1. Exceptions as Control Flow

**Anti-Pattern:**
```python
def get_data():
    try:
        return fetch_from_primary_api()
    except TimeoutError:
        try:
            return fetch_from_backup_api()
        except TimeoutError:
            return {"status": "error"}
```

**Correct Approach:**
```python
def fetch_from_api(key) -> dict:
    value = await client.get(key)
    if value is None:
        return {"status": "error", "msg": "Not found"}
    return {"status": "ok", "data": value}

def get_data():
    result = fetch_from_api("primary:key")
    if result["status"] == "error":
        result = fetch_from_api("backup:key")
    return result
```

**Why This Fails:**
- Exceptions are expensive (performance cost)
- Code becomes hard to read (nested try/except)
- Hides real problems
- Doesn't scale

**Demo Output:**
```
=== ANTI-PATTERN: Exceptions as Control Flow ===
Result: {'status': 'ok', 'data': b'primary_data'}

=== CORRECT: Status-Based Returns ===
Result: {'status': 'ok', 'data': b'primary_data'}
```

---

### 2. Static Method-Only Classes

**Anti-Pattern:**
```python
class CacheUtils:
    @staticmethod
    async def get_user(client, user_id):
        return await client.get(f"user:{user_id}")
    
    @staticmethod
    async def set_user(client, user_id, data):
        await client.set(f"user:{user_id}", data)
```

**Correct Approach:**
```python
# Just use module-level functions
async def get_user(client, user_id):
    return await client.get(f"user:{user_id}")

async def set_user(client, user_id, data):
    await client.set(f"user:{user_id}", data)
```

**Why This Fails:**
- Unnecessary boilerplate
- Namespace overkill (Python has modules)
- No real benefit
- Not object-oriented, just namespacing with ceremony

**Demo Output:**
```
=== ANTI-PATTERN: Static Method-Only Class ===
User from static class: b'Alice'

=== CORRECT: Module-Level Functions ===
User from function: b'Bob'
```

---

### 3. Tight Coupling (No Abstraction)

**Anti-Pattern:**
```python
class UserService:
    def __init__(self, host, port):
        self.config = GlideClientConfiguration([NodeAddress(host, port)])
        self.client = None
    
    async def connect(self):
        self.client = await GlideClient.create(self.config)
```

**Correct Approach:**
```python
from typing import Protocol

class CacheClient(Protocol):
    async def get(self, key: str) -> str: ...
    async def set(self, key: str, value: str): ...

class UserService:
    def __init__(self, cache: CacheClient):
        self.cache = cache
```

**Why This Fails:**
- Hard to test (requires real Valkey connection)
- Cannot swap implementations
- Violates Dependency Inversion Principle
- High coupling to concrete class

**Demo Output:**
```
=== ANTI-PATTERN: Tight Coupling ===
User from tightly coupled service: b'Alice'

=== CORRECT: Protocol-Based Abstraction ===
User from abstracted service: b'Bob'
```

---

### 4. Wildcard Imports

**Anti-Pattern:**
```python
from glide import *

client = GlideClient.create(...)  # Where did this come from?
```

**Correct Approach:**
```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

client = await GlideClient.create(...)  # Clear origin
```

**Why This Fails:**
- Namespace pollution
- Name collisions
- Static analysis becomes useless
- Cognitive load (where did this function come from?)

**Demo Output:**
```
=== ANTI-PATTERN: Wildcard Imports ===
# from glide import *  # ❌ Namespace pollution

=== CORRECT: Explicit Imports ===
# from glide import GlideClient, GlideClientConfiguration  # ✅ Clear
```

---

## Key Takeaways

1. **Exceptions should be exceptional** - Use status returns for normal logic
2. **Functions over classes** - Don't wrap functions in static-only classes
3. **Depend on abstractions** - Use Protocols for testability and flexibility
4. **Explicit imports** - Never use wildcard imports

## Python Anti-Patterns Summary

| Anti-Pattern | Problem | Solution |
|-------------|---------|----------|
| Exceptions as control flow | Expensive, hard to read | Status-based returns |
| Static method-only classes | Unnecessary boilerplate | Module-level functions |
| Tight coupling | Hard to test, inflexible | Protocol-based abstraction |
| Wildcard imports | Namespace pollution | Explicit imports |

## Related Resources

- [The Zen of Python](https://peps.python.org/pep-0020/)
- [Python typing.Protocol docs](https://docs.python.org/3/library/typing.html#typing.Protocol)
- [Original Article](https://medium.com/@BuildShift/10-python-anti-patterns-ruining-your-code-and-what-to-do-instead-e304c457bc98)
