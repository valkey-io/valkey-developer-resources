# Per-User Isolation

> Give each user a private view of one shared knowledge base — documents uploaded by a user are
visible only to them, while shared documents are visible to everyone.

**Intermediate** · Python · ~15 min

**Who is this for:** Developers building multi-tenant AI applications where each user's
knowledge must be isolated, but shared organizational knowledge stays accessible to all.

## How Per-User Isolation Works

ValkeyDB stores an owner TAG field (`user_id`) on every document chunk. When searching:

- **User search** (`user_id="alice"`) → returns Alice's docs + shared docs
- **Admin search** (`user_id=None`) → returns all docs across all users
- **Isolation guarantee** → Alice cannot see Bob's documents

```text
Insert(user_id="alice", doc) → HSET ... user_id=alice
Insert(user_id=None, doc)    → HSET ... user_id=__shared__

Search(user_id="alice") → FT.SEARCH @user_id:{alice|__shared__}
Search(user_id=None)    → FT.SEARCH (no scope — sees everything)
```

## Prerequisites

- Completed [02 - Knowledge Base](02-knowledge-base.md) (Valkey + Ollama running)
- `pip install "agno[valkey,ollama]==2.8.0"`

## Step 1: Create the Vector Store

```python
import asyncio
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.knowledge.document.base import Document
from agno.vectordb.valkey import ValkeyDB
from agno.vectordb.search import SearchType

embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768)

vector_db = ValkeyDB(
    index_name="per_user_demo",
    host="localhost",
    port=6379,
    embedder=embedder,
    search_type=SearchType.vector,
)
```

## Step 2: Insert User-Scoped and Shared Documents

```python
async def setup_data():
    await vector_db.async_create()

    # Alice's private document
    await vector_db.async_insert(
        content_hash="alice_salary",
        documents=[Document(name="alice_salary", content="Alice's salary is $180,000. Reviewed annually in March.")],
        user_id="alice",
    )

    # Bob's private document
    await vector_db.async_insert(
        content_hash="bob_salary",
        documents=[Document(name="bob_salary", content="Bob's salary is $215,000. Reviewed annually in June.")],
        user_id="bob",
    )

    # Shared document (no user_id → visible to everyone)
    await vector_db.async_insert(
        content_hash="company_holidays",
        documents=[Document(name="holidays", content="The company is closed on January 1, July 4, and December 25.")],
    )
```

## Step 3: Verify Isolation

```python
async def verify_isolation():
    # Alice can see her own salary + shared docs
    alice_results = await vector_db.async_search(
        "What is Alice's salary?", limit=5, user_id="alice"
    )
    print(f"Alice's search: {len(alice_results)} results")
    for doc in alice_results:
        print(f"  - {doc.content[:60]}")

    # Alice CANNOT see Bob's salary
    alice_bob = await vector_db.async_search(
        "What is Bob's salary?", limit=5, user_id="alice"
    )
    bob_leak = [d for d in alice_bob if "215,000" in d.content]
    assert not bob_leak, "Isolation broken!"
    print("\n  ✓ Isolation holds: Bob's salary not visible to Alice")

    # Bob can see shared holidays
    bob_holidays = await vector_db.async_search(
        "When is the company closed?", limit=5, user_id="bob"
    )
    print(f"\nBob's holiday search: {len(bob_holidays)} results")
    for doc in bob_holidays:
        print(f"  - {doc.content[:60]}")

    # Admin sees everything (user_id=None)
    admin_results = await vector_db.async_search(
        "salary", limit=10, user_id=None
    )
    print(f"\nAdmin search: {len(admin_results)} results (sees all)")
```

## Step 4: Run It

```python
async def main():
    await setup_data()
    await verify_isolation()
    await vector_db.async_drop()

asyncio.run(main())
```

Expected output:

```text
Alice's search: 2 results
  - Alice's salary is $180,000. Reviewed annually in March.
  - The company is closed on January 1, July 4, and December 25.

  ✓ Isolation holds: Bob's salary not visible to Alice

Bob's holiday search: 2 results
  - The company is closed on January 1, July 4, and December 25.
  - Bob's salary is $215,000. Reviewed annually in June.

Admin search: 3 results (sees all)
```

## How It Works

| Concept | Implementation |
| ------- | -------------- |
| Owner tracking | `user_id` TAG field on every HASH key |
| Shared bucket | Chunks with `user_id=__shared__` sentinel |
| Scoped search | `@user_id:{alice\|__shared__}` pre-filter in FT.SEARCH |
| Admin access | No scope clause → sees all chunks |
| Key scoping | `hash(doc_id + user_id)` → same content for different users gets distinct keys |
| Validation | Rejects `user_id` with `{}`, `*`, `?`, empty string, or sentinel values |

## Security Considerations

The per-user isolation is enforced **server-side** in the FT.SEARCH query. However:

- The `user_id` is caller-provided — your application must authenticate users and pass the
  correct `user_id`. Agno does not verify identity.
- A user with raw Valkey access (via `valkey-cli`) can read any key. Restrict network access
  to the Valkey instance.
- The admin view (`user_id=None`) has no scope — use it only in trusted backend contexts.

## Cleanup

```bash
docker stop valkey && docker rm valkey
```

---

[← 02 - Knowledge Base](02-knowledge-base.md)
