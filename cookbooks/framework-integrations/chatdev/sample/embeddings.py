# -*- coding: utf-8 -*-
"""Embedding providers for the ValkeyMemory sample.

The default provider (`LocalDeterministicEmbedding`) needs no network
access and no API key, so the sample and its tests run anywhere. It is a
deterministic hashing embedding — NOT a real semantic model — intended
only to exercise ValkeyMemory's store/retrieve/index mechanics.

`ValkeyMemory` probes the embedding dimension at runtime by calling
`get_embedding()` once (see `_ensure_index()` in valkey_memory.py), so
swapping providers here changes the FT index dimension automatically.

Optional providers (OpenAI, Ollama) are included for readers who want to
exercise real semantic similarity, but neither is a default dependency —
see requirements.txt, which pins only `valkey-glide-sync` and `pytest`.
Install the extra package yourself if you use one of these:

    pip install openai==1.54.4       # for OpenAIEmbedding
    # Ollama needs no extra pip package; it calls a local HTTP server
    # (https://ollama.com) via urllib from the standard library.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from abc import ABC, abstractmethod

DEFAULT_DIMENSION = 64


class EmbeddingProvider(ABC):
    """Minimal interface ValkeyMemory depends on."""

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """Return a fixed-length embedding vector for `text`."""
        raise NotImplementedError


class LocalDeterministicEmbedding(EmbeddingProvider):
    """Default, no-network, no-API-key embedding provider.

    Hashes each word into a fixed-dimension bag-of-words vector and
    L2-normalizes it. Shared words between two texts land in the same
    dimensions, so cosine similarity is meaningfully higher for related
    text than unrelated text — enough to demonstrate KNN ranking, filtering,
    and thresholding without a real model. The dimension is fixed at
    construction time and reported to callers (and to ValkeyMemory's index
    probe) via `get_embedding()`'s return length.
    """

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        self.dimension = dimension

    def get_embedding(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for word in text.lower().split():
            digest = hashlib.md5(word.encode("utf-8")).hexdigest()
            vec[int(digest, 16) % self.dimension] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class OpenAIEmbedding(EmbeddingProvider):
    """Optional: real semantic embeddings via the OpenAI API.

    Requires `pip install openai==1.54.4` (not installed by default — see
    requirements.txt) and an `OPENAI_API_KEY` environment variable.
    `text-embedding-3-small` returns 1536-dimensional vectors; ValkeyMemory
    adapts its index dimension automatically on first use.
    """

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OpenAIEmbedding requires the 'openai' package. "
                "Install it with: pip install openai==1.54.4"
            ) from exc
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def get_embedding(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)


class OllamaEmbedding(EmbeddingProvider):
    """Optional: local, self-hosted embeddings via Ollama.

    Requires a running Ollama server (https://ollama.com) with an embedding
    model pulled, e.g. `ollama pull nomic-embed-text`. No pip package is
    required — this calls Ollama's local HTTP API with the standard library.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_embedding(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return list(body["embedding"])
