# -*- coding: utf-8 -*-
"""Cookbook 01 - Getting Started with ChatDev + Valkey (LOCAL EMBEDDINGS).

Same as quick_start.py but uses sentence-transformers instead of OpenAI.
No API key required.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    cd ChatDev && pip install -e ".[valkey]"
    pip install sentence-transformers

Note: Run this script from the ChatDev project root (where runtime/ is importable).
"""

from __future__ import annotations

import sys
import os

# Add ChatDev project root to path (when running from outside the project)
CHATDEV_ROOT = os.environ.get("CHATDEV_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CHATDEV_ROOT)

from entity.configs.node.memory import MemoryStoreConfig
from runtime.node.agent.memory.builtin_stores import MemoryFactory
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryWritePayload,
)


def main() -> None:
    """Run the quick start example with local embeddings."""
    print("=== ChatDev + Valkey: Quick Start (Local Embeddings) ===\n")

    # 1. Define the memory store config using local sentence-transformers
    store_data = {
        "name": "chatdev_memory",
        "type": "valkey",
        "config": {
            "host": "localhost",
            "port": 6379,
            "index_name": "quickstart_local",
            "key_prefix": "quickstart_local:",
            "ttl_seconds": 300,
            "embedding": {
                "provider": "local",
                "model": "all-MiniLM-L6-v2",
                "params": {
                    "model_path": "sentence-transformers/all-MiniLM-L6-v2",
                    "device": "cpu",
                },
            },
        },
    }
    store = MemoryStoreConfig.from_dict(store_data, path="quickstart")
    print(f"Configured store: type={store.type}, index={store.config.index_name}")

    # 2. Create the ValkeyMemory instance via the factory
    try:
        memory = MemoryFactory.create_memory(store)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        print("  Make sure Valkey is running and sentence-transformers is installed.")
        sys.exit(1)

    print(f"Created ValkeyMemory (name={memory.name})\n")

    # 3. Store some memories using update()
    print("--- Storing Memories ---")
    inputs = [
        ("coder", "Python is great for data science and ML pipelines"),
        ("designer", "The dashboard should use a dark theme with high contrast"),
        ("coder", "We need integration tests for the authentication module"),
        ("designer", "Use material design icons for the navigation bar"),
    ]

    for role, text in inputs:
        payload = MemoryWritePayload(
            agent_role=role,
            inputs_text=text,
            input_snapshot=MemoryContentSnapshot(text=text),
            output_snapshot=None,
        )
        memory.update(payload)
        print(f"  [{role}] {text}")

    # 4. Retrieve relevant memories
    #    similarity_threshold=-1.0 means "return all top_k results regardless of score"
    print("\n--- Retrieving Memories (query='Python testing') ---")
    query = MemoryContentSnapshot(text="Python testing")
    results = memory.retrieve("coder", query, top_k=2, similarity_threshold=-1.0)

    for item in results:
        score = item.metadata.get("score", 0)
        print(f"  [{score:.3f}] {item.content_summary}")

    # 5. Check memory count
    count = memory.count_memories()
    print(f"\nTotal memories stored: {count}")

    print("\nDone!")


if __name__ == "__main__":
    main()
