# Valkey with Haystack

> Use Valkey Search as a Haystack document store and vector retriever for local RAG experiments.

**Who is this for:** Python developers building Haystack pipelines who want a Valkey-backed document store and vector search.

Haystack is an open-source framework maintained by deepset for building search
and RAG applications. The `valkey-haystack` integration exposes Valkey-backed
document storage and retrieval as Haystack components.

The default path uses fixed four-dimensional vectors, so it needs no API key,
model download, or external service. The numbered pages also show where to add
Haystack embedders when a model-generated embedding workflow is appropriate.

## Prerequisites

- Python 3.10 or newer
- Docker or Podman with Compose support
- The dependencies and setup in the [runnable sample](sample/README.md)

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install the Haystack Valkey integration, connect to Valkey Search, and retrieve documents with deterministic embeddings. | Beginner, ~10 min, Python |
| 02 | <nobr>[RAG Pipeline](02-rag-pipeline.md)</nobr> | Separate indexing and query pipelines, then use retrieved documents as local answer context. | Intermediate, ~20 min, Python |
