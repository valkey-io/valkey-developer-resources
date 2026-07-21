"""CrewAI + Valkey Memory demo: agents with persistent Valkey-backed memory.

Corresponds to cookbook: 03-agent-memory.md.

Requires:
- Valkey running on localhost:6379 with the search module
- Ollama running with models: nomic-embed-text, llama3.2:1b

This demo shows CrewAI's unified Memory system using ValkeyStorageBackend
as the durable storage layer. Memories persist across script executions.
"""

from __future__ import annotations

import os

from crewai import Memory

from valkey_storage import ValkeyStorageBackend


# Ollama embedding config for CrewAI Memory
EMBEDDER_CONFIG = {
    "provider": "ollama",
    "config": {
        "model_name": "nomic-embed-text",
    },
}

# Embedding dimension for nomic-embed-text
EMBEDDING_DIM = 768


def create_memory() -> tuple[Memory, ValkeyStorageBackend]:
    """Create a CrewAI Memory backed by Valkey.

    Returns the Memory instance and the backend (for explicit close).
    """
    host = os.environ.get("VALKEY_HOST", "localhost")
    port = int(os.environ.get("VALKEY_PORT", "6379"))

    backend = ValkeyStorageBackend(
        host=host,
        port=port,
        embedding_dim=EMBEDDING_DIM,
    )

    memory = Memory(
        storage=backend,
        llm="ollama/llama3.2:1b",
        embedder=EMBEDDER_CONFIG,
    )

    return memory, backend


def main() -> None:
    """Demonstrate persistent memory with CrewAI + Valkey."""
    memory, backend = create_memory()
    try:
        # Start clean for idempotent runs
        backend.reset()

        print("=== CrewAI + Valkey Memory Demo ===\n")

        # Store memories
        print("Storing memories...")
        memory.remember("Valkey uses HNSW algorithm for fast vector similarity search.")
        memory.remember("Always close GLIDE clients explicitly to prevent connection leaks.")
        memory.remember("Use TAG fields for exact-match filtering in FT.SEARCH queries.")
        print(f"  Stored 3 memories (total in Valkey: {backend.count()})\n")

        # Recall by semantic similarity
        print("Recalling: 'How does vector search work?'")
        matches = memory.recall("How does vector search work?")
        if matches:
            for m in matches:
                print(f"  [{m.score:.2f}] {m.record.content}")
        else:
            print("  No matches found")

        print()

        # Recall a different topic
        print("Recalling: 'connection management best practices'")
        matches = memory.recall("connection management best practices")
        if matches:
            for m in matches:
                print(f"  [{m.score:.2f}] {m.record.content}")
        else:
            print("  No matches found")

        print("\nMemories persist in Valkey across script executions.")
        print(f"Total records in Valkey: {backend.count()}")

    finally:
        backend.close()


if __name__ == "__main__":
    main()
