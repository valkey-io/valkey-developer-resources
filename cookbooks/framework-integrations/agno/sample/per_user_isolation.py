"""Agno + Valkey: Per-user knowledge isolation demo.

Demonstrates TAG-based user isolation in ValkeyDB — each user sees only
their own documents plus shared ones.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    ollama pull nomic-embed-text
    pip install "agno[valkey,ollama]==2.8.0"
    python per_user_isolation.py
"""

from __future__ import annotations

import asyncio

from agno.knowledge.document.base import Document
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.vectordb.search import SearchType
from agno.vectordb.valkey import ValkeyDB

INDEX_NAME = "per_user_isolation_demo"


async def main() -> None:
    embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768)

    vector_db = ValkeyDB(
        index_name=INDEX_NAME,
        host="localhost",
        port=6379,
        embedder=embedder,
        search_type=SearchType.vector,
    )

    # Clean slate
    try:
        await vector_db.async_drop()
    except Exception:
        pass
    await vector_db.async_create()

    # Insert user-scoped documents
    await vector_db.async_insert(
        content_hash="alice_salary",
        documents=[Document(name="alice_salary", content="Alice's salary is $180,000. Reviewed annually in March.")],
        user_id="alice",
    )
    await vector_db.async_insert(
        content_hash="bob_salary",
        documents=[Document(name="bob_salary", content="Bob's salary is $215,000. Reviewed annually in June.")],
        user_id="bob",
    )
    # Shared document (no user_id)
    await vector_db.async_insert(
        content_hash="company_holidays",
        documents=[Document(name="holidays", content="The company is closed on January 1, July 4, and December 25.")],
    )

    print("=== Per-User Isolation Demo ===\n")

    # Alice sees her salary + shared docs
    alice_results = await vector_db.async_search("What is Alice's salary?", limit=5, user_id="alice")
    print(f"Alice asks about salary → {len(alice_results)} results")
    for doc in alice_results:
        print(f"  - {doc.content[:70]}")

    # Alice cannot see Bob's salary
    alice_bob = await vector_db.async_search("What is Bob's salary?", limit=5, user_id="alice")
    bob_leak = [d for d in alice_bob if "215,000" in d.content]
    assert not bob_leak, "ISOLATION BROKEN: Alice saw Bob's salary!"
    print("\n  ✓ Isolation holds: Bob's salary NOT visible to Alice")

    # Bob sees shared holidays
    bob_holidays = await vector_db.async_search("When is the company closed?", limit=5, user_id="bob")
    print(f"\nBob asks about holidays → {len(bob_holidays)} results")
    for doc in bob_holidays:
        print(f"  - {doc.content[:70]}")

    # Admin (user_id=None) sees everything
    admin_results = await vector_db.async_search("salary", limit=10, user_id=None)
    print(f"\nAdmin search → {len(admin_results)} results (sees all)")
    for doc in admin_results:
        print(f"  - {doc.content[:70]}")

    # Cleanup
    await vector_db.async_drop()
    print("\n✓ Demo complete")


if __name__ == "__main__":
    asyncio.run(main())
