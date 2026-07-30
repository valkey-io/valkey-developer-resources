"""PraisonAI + Valkey: State persistence and vector knowledge demo.

Demonstrates:
- ValkeyStateStore for agent session history across restarts
- ValkeyVectorKnowledgeStore for semantic knowledge retrieval with HNSW

No LLM or API key required — demo_state_store uses hardcoded replies to show
the persistence mechanics without a real agent. See cookbook 02 for the live-
agent version that calls agent.start(). demo_vector_knowledge uses sentence-
transformers locally.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    pip install "praisonai[valkey]==4.6.157" "sentence-transformers==3.3.1"
    python main.py
"""

from __future__ import annotations

import os

from sentence_transformers import SentenceTransformer

from praisonai.persistence.knowledge.base import KnowledgeDocument
from praisonai.persistence.knowledge.valkey_vector import ValkeyVectorKnowledgeStore
from praisonai.persistence.state.valkey import ValkeyStateStore

# --- Connection settings ---
VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD") or None

COLLECTION = "agent_kb"
DIM = 384  # all-MiniLM-L6-v2 output dimension

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    return embedding_model.encode(text, normalize_embeddings=True).tolist()


# -----------------------------------------------------------------
# Part 1: Agent State Persistence (ValkeyStateStore)
# -----------------------------------------------------------------


def demo_state_store() -> None:
    """Demonstrate key-value state persistence with ValkeyStateStore."""
    print("=== Part 1: Agent State Persistence ===\n")

    store = ValkeyStateStore(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        password=VALKEY_PASSWORD,
        prefix="praisonai:demo:state:",
    )

    try:
        # Simulate a multi-turn session
        history: list[dict] = store.get("history") or []
        run_count = store.incr("run_count")

        exchanges = [
            ("What is Valkey?", "Valkey is an open-source, high-performance in-memory key-value store."),
            ("Who maintains it?", "Valkey is maintained by the Linux Foundation Valkey community."),
        ]

        for user_msg, mock_reply in exchanges:
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": mock_reply})
            print(f"User   : {user_msg}")
            print(f"Agent  : {mock_reply}\n")

        store.set("history", history)
        store.hset("meta", "last_query", exchanges[-1][0])
        store.hset("meta", "run_count", str(run_count))

        # Verify persistence
        loaded = store.get("history") or []
        assert len(loaded) == len(history), f"History round-trip failed: expected {len(history)}, got {len(loaded)}"
        assert loaded[0]["role"] == "user", "First message should be user role"
        meta = store.hgetall("meta")
        assert "run_count" in meta, "run_count missing from meta hash"
        assert "last_query" in meta, "last_query missing from meta hash"
        print(f"Run count  : {run_count}")
        print(f"Metadata   : {meta}")
        print(f"History    : {len(loaded)} messages persisted in Valkey")

    finally:
        store.close()


# -----------------------------------------------------------------
# Part 2: Vector Knowledge Retrieval (ValkeyVectorKnowledgeStore)
# -----------------------------------------------------------------

KNOWLEDGE = [
    {"id": "doc1", "content": "Valkey is an open-source, high-performance in-memory key-value store forked from Redis 7.2."},
    {"id": "doc2", "content": "ValkeySearch adds FT.CREATE and FT.SEARCH commands for full-text and vector similarity search."},
    {"id": "doc3", "content": "HNSW (Hierarchical Navigable Small World) is a graph-based approximate nearest-neighbour index."},
    {"id": "doc4", "content": "Valkey GLIDE is the official client with a Rust core supporting standalone and cluster modes."},
    {"id": "doc5", "content": "PraisonAI is a multi-agent framework supporting OpenAI-compatible LLMs with pluggable memory backends."},
    {"id": "doc6", "content": "ElastiCache for Valkey is a managed Valkey service on AWS with automatic failover and Multi-AZ support."},
]


def demo_vector_knowledge() -> None:
    """Demonstrate semantic knowledge retrieval with ValkeyVectorKnowledgeStore."""
    print("=== Part 2: Vector Knowledge Retrieval ===\n")

    store = ValkeyVectorKnowledgeStore(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        password=VALKEY_PASSWORD,
        prefix="praisonai:demo:kb:",
    )

    try:
        # Create index and ingest documents
        store.create_collection(COLLECTION, dimension=DIM, distance="cosine")
        documents = [
            KnowledgeDocument(
                id=d["id"],
                content=d["content"],
                embedding=embed(d["content"]),
            )
            for d in KNOWLEDGE
        ]
        ids = store.insert(COLLECTION, documents)
        print(f"Indexed {len(ids)} documents.\n")

        # Query the knowledge base
        queries = [
            "What client library should I use for Valkey?",
            "How does vector search work in Valkey?",
            "Tell me about managed Valkey on AWS",
        ]
        for q in queries:
            results = store.search(COLLECTION, query_embedding=embed(q), limit=2)
            assert len(results) >= 1, f"Expected at least 1 result for: {q}"
            print(f"Q: {q}")
            for doc in results:
                print(f"  -> {doc.content}")
            print()

    finally:
        store.close()


def main() -> None:
    demo_state_store()
    demo_vector_knowledge()
    print("Demo complete.")


if __name__ == "__main__":
    main()
