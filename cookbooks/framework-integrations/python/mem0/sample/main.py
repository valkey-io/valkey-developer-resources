"""Runnable Mem0 + Valkey example with deterministic local embeddings."""

from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("MEM0_TELEMETRY", "false")

from mem0 import Memory
from mem0.embeddings.mock import MockEmbeddings

COLLECTION_NAME = os.environ.get("MEM0_COLLECTION", "mem0_demo")
EMBEDDING_DIMENSIONS = 10


def build_memory(collection_name: str = COLLECTION_NAME) -> Memory:
    """Create Mem0 with its Valkey vector store and local test configuration."""
    memory = Memory.from_config(
        {
            "vector_store": {
                "provider": "valkey",
                "config": {
                    "valkey_url": os.environ.get(
                        "VALKEY_URL", "valkey://localhost:6379?socket_timeout=5"
                    ),
                    "collection_name": collection_name,
                    "embedding_model_dims": EMBEDDING_DIMENSIONS,
                    "index_type": "hnsw",
                    "hnsw_m": 16,
                    "hnsw_ef_construction": 200,
                    "hnsw_ef_runtime": 10,
                },
            },
            # This sample is credential-free: infer=False skips LLM fact
            # extraction and the embedder is replaced with MockEmbeddings below,
            # so neither provider below is ever contacted. The nominal "openai"
            # provider is used only because it constructs lazily (no connection
            # at init). Real usage configures Ollama per the cookbook.
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": "unused-with-infer-false",
                    "model": "gpt-4o-mini",
                },
            },
            # Replaced with Mem0's built-in local mock after construction.
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": "unused-with-local-mock",
                    "model": "text-embedding-3-small",
                },
            },
            "history_db_path": os.path.join(
                tempfile.gettempdir(), f"mem0-valkey-{collection_name}.db"
            ),
        }
    )
    # Internal Mem0 attribute; this sample is pinned to mem0ai==2.0.0.
    memory.embedding_model = MockEmbeddings()
    return memory


def reset_memory(memory: Memory) -> None:
    """Remove sample keys and recreate the Mem0 index for an idempotent run.

    Uses Mem0 internal ``vector_store.client`` and ``collection_name``
    attributes; this sample is pinned to mem0ai==2.0.0.
    """
    valkey_client = memory.vector_store.client
    for key in valkey_client.scan_iter(
        match=f"mem0:{memory.collection_name}:*"
    ):
        valkey_client.delete(key)
    memory.reset()


def run_demo() -> None:
    memory = build_memory()
    reset_memory(memory)
    try:
        memory.add(
            [{"role": "user", "content": "Alice prefers Python for data work."}],
            user_id="alice",
            infer=False,
        )
        memory.add(
            [{"role": "user", "content": "Bob prefers TypeScript for web apps."}],
            user_id="bob",
            infer=False,
        )

        alice_results = memory.search(
            "What programming language does Alice prefer?",
            filters={"user_id": "alice"},
            # Mem0 2.0.0 exposes Valkey cosine distance; the deterministic
            # mock returns distance 0.0 for every vector, so include exact
            # matches in this credential-free demonstration.
            threshold=0.0,
        )
        bob_memories = memory.get_all(filters={"user_id": "bob"})
        assert alice_results["results"][0]["memory"] == (
            "Alice prefers Python for data work."
        )
        assert bob_memories["results"][0]["memory"] == (
            "Bob prefers TypeScript for web apps."
        )

        print("=== Mem0 + Valkey Demo ===")
        print("Alice search:")
        print(json.dumps(alice_results["results"], indent=2))
        print("Bob memories:")
        print(json.dumps(bob_memories["results"], indent=2))
    finally:
        reset_memory(memory)
        memory.close()


if __name__ == "__main__":
    run_demo()
