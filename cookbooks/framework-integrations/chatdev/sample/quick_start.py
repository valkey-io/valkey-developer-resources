# -*- coding: utf-8 -*-
"""Cookbook 01 - Getting Started with ChatDev + Valkey.

Demonstrates: creating a ValkeyMemory store, storing memories via update(),
retrieving relevant memories via retrieve(), and verifying persistence.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    cd ChatDev && pip install -e ".[valkey]"
    export API_KEY="sk-..."
    export BASE_URL="https://api.openai.com/v1"

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
    """Run the quick start example."""
    print("=== ChatDev + Valkey: Quick Start ===\n")

    # --- Validate API key ---
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("ERROR: API_KEY environment variable is not set.")
        print("  export API_KEY='sk-...'")
        sys.exit(1)

    # 1. Define the memory store config (same structure as workflow YAML)
    store_data = {
        "name": "chatdev_memory",
        "type": "valkey",
        "config": {
            "host": "localhost",
            "port": 6379,
            "index_name": "quickstart_memory",
            "key_prefix": "quickstart:",
            "ttl_seconds": 300,
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
            },
        },
    }
    store = MemoryStoreConfig.from_dict(store_data, path="quickstart")
    print(f"Configured store: type={store.type}, index={store.config.index_name}")

    # 2. Create the ValkeyMemory instance via the factory
    memory = MemoryFactory.create_memory(store)
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
