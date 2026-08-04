"""Shared Ollama/Cognee configuration bootstrap for the cognee cookbook samples."""

from __future__ import annotations

import os
import pathlib


def configure_ollama_env() -> None:
    """Set Cognee's LLM/embedding env vars to local Ollama defaults.

    Must be called before any `cognee` import — Cognee reads these at import time.
    Uses `setdefault` so a real deployment's env vars are never overridden.
    """
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_MODEL", "qwen2.5:7b")
    os.environ.setdefault("LLM_ENDPOINT", "http://localhost:11434/v1")
    os.environ.setdefault("LLM_API_KEY", "ollama")
    os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
    os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text")
    os.environ.setdefault("EMBEDDING_ENDPOINT", "http://localhost:11434/api/embeddings")
    os.environ.setdefault("EMBEDDING_API_KEY", "ollama")
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
    os.environ.setdefault("HUGGINGFACE_TOKENIZER", "nomic-ai/nomic-embed-text-v1.5")


async def bootstrap_cognee(sample_dir: pathlib.Path) -> None:
    """Point Cognee's system/data dirs and vector DB at this sample, then clear old state.

    Call after `configure_ollama_env()`. Imports `cognee.config`/`cognee.prune`
    lazily so this module never forces a `cognee` import before env vars are set.
    """
    from cognee import config, prune

    config.system_root_directory(str(sample_dir / ".cognee-system"))
    config.data_root_directory(str(sample_dir / ".cognee-data"))
    config.set_vector_db_config({
        "vector_db_provider": "valkey",
        # Use "valkeys://..." (with 's') for TLS connections in production
        "vector_db_url": os.getenv("VECTOR_DB_URL", "valkey://localhost:6379"),
    })

    print("Pruning existing data...")
    await prune.prune_data()
    await prune.prune_system(metadata=True)
