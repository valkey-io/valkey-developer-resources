# -*- coding: utf-8 -*-
"""Quick start: exercise ValkeyMemory's store/retrieve/TTL behavior end to end.

Run against a local valkey-bundle (Search module required):

    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    python quick_start.py

Config via environment (defaults shown):
    VALKEY_HOST=localhost
    VALKEY_PORT=6379
    VALKEY_REQUEST_TIMEOUT_MS=5000

This script asserts expected behavior at every step (not just prints), so
running it catches regressions the same way the test suite does.
"""

from __future__ import annotations

import sys
import time

from valkey_memory import ValkeyMemory, ValkeyMemoryConfig


def main() -> None:
    print("=== ChatDev + Valkey: Quick Start ===\n")

    config = ValkeyMemoryConfig(
        index_name="quickstart_memory",
        key_prefix="quickstart:",
        ttl_seconds=300,
    )
    memory = ValkeyMemory(config)

    try:
        # --- Store memories for two different agent roles ---
        print("--- Storing Memories ---")
        inputs = [
            ("coder", "Python is great for data science and ML pipelines"),
            ("designer", "The dashboard should use a dark theme with high contrast"),
            ("coder", "We need integration tests for the authentication module"),
            ("designer", "Use material design icons for the navigation bar"),
        ]
        stored_keys = []
        for role, text in inputs:
            key = memory.update(agent_role=role, text=text)
            stored_keys.append(key)
            print(f"  [{role}] {text} -> {key}")
        assert len(stored_keys) == 4, f"expected 4 stored keys, got {len(stored_keys)}"
        assert all(k.startswith("quickstart:") for k in stored_keys), "key prefix mismatch"

        # Indexing is asynchronous relative to the write; give it a brief
        # moment before querying. A production system would poll instead.
        time.sleep(0.3)

        # --- Filtered retrieval: only 'coder' memories ---
        print("\n--- Filtered Retrieval (agent_role='coder', query='Python testing') ---")
        coder_results = memory.retrieve(
            agent_role="coder", query_text="Python testing", top_k=2, similarity_threshold=-1.0
        )
        for item in coder_results:
            score = item.similarity if item.similarity is not None else 0.0
            print(f"  [{score:.3f}] ({item.agent_role}) {item.content_summary}")
        assert coder_results, "expected at least one coder memory"
        assert all(item.agent_role == "coder" for item in coder_results), (
            "agent_role filter leaked a memory from another role"
        )

        # --- Unfiltered retrieval: across all agent roles ---
        print("\n--- Unfiltered Retrieval (agent_role=None, query='design theme') ---")
        all_results = memory.retrieve(
            agent_role=None, query_text="design theme", top_k=4, similarity_threshold=-1.0
        )
        for item in all_results:
            score = item.similarity if item.similarity is not None else 0.0
            print(f"  [{score:.3f}] ({item.agent_role}) {item.content_summary}")
        assert all_results, "expected results from the unfiltered query"
        seen_roles = {item.agent_role for item in all_results}
        assert "designer" in seen_roles, "unfiltered query should surface designer memories too"

        # --- Threshold filtering ---
        print("\n--- Threshold Filtering (similarity_threshold=0.99) ---")
        strict_results = memory.retrieve(
            agent_role="coder", query_text="completely unrelated astrophysics topic", top_k=2,
            similarity_threshold=0.99,
        )
        print(f"  {len(strict_results)} result(s) passed the 0.99 threshold")
        assert len(strict_results) == 0, "an unrelated query should not pass a 0.99 threshold"

        # --- Count ---
        count = memory.count_memories()
        print(f"\nTotal memories stored: {count}")
        assert count == 4, f"expected 4 stored memories, got {count}"

        print("\nAll quick start checks passed.")
    finally:
        # Always close the connection, even if an assertion above failed.
        memory.close()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\nAssertion failed: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - friendly top-level message
        print(f"\nError: {exc}")
        print("Is Valkey running? Try:")
        print("  docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0")
        sys.exit(1)
