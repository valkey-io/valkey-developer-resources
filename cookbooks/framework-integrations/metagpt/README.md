# MetaGPT + Valkey

> 3 cookbooks for using Valkey as a RAG vector store backend in MetaGPT — the multi-agent framework where LLM-based roles collaborate like a software company.

## What is MetaGPT?

[MetaGPT](https://github.com/FoundationAgents/MetaGPT) is a multi-agent framework that assigns roles (product manager, architect, engineer) to LLMs so they collaborate on complex tasks. Its RAG module
supports pluggable vector stores through a `ConfigBasedFactory` pattern (the same pattern used by FAISS, Chroma, and Elasticsearch). Valkey plugs in as a **vector store** for retrieval-augmented
generation: store document embeddings with HNSW or FLAT indexing and run KNN similarity search optimized for low latency.

MetaGPT is a [FoundationAgents](https://github.com/FoundationAgents) open-source project (formerly hosted at `geekan/MetaGPT`, which now redirects to the FoundationAgents organization).

The integration uses the **synchronous** `valkey-glide` client (the `glide_sync` module, shipped as the `valkey-glide-sync` package) to stay consistent with MetaGPT's other synchronous RAG backends.

## Upstream Status

The `ValkeyVectorStore` RAG backend is proposed in upstream pull request [FoundationAgents/MetaGPT#2063](https://github.com/FoundationAgents/MetaGPT/pull/2063), which is **open and unreviewed** at
the time of writing. These cookbooks describe the design from that PR, and the [`sample/`](01-getting-started.md#try-it-the-runnable-sample) code independently reproduces its verified Valkey behavior
— the same `FT.CREATE` schema, the same key prefix pattern, and the same atomic batch semantics — without importing MetaGPT as a dependency. The Valkey RAG backend is not yet part of any published
`metagpt` release on PyPI. If PR #2063 changes before merging, the exact field names or defaults in these cookbooks may need to be revisited against the merged version.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Map the proposed MetaGPT + Valkey RAG configuration, start Valkey with the search module, and connect with the synchronous GLIDE client. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Store for RAG](02-vector-store-rag.md)</nobr> | Use `ValkeyVectorStore` to store embeddings as JSON documents with an HNSW index and run KNN similarity search via `FT.SEARCH`. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production](03-production.md)</nobr> | Configure TLS, tune the HNSW index, monitor index health, and deploy against a managed Valkey service. | Advanced, ~15 min, Python |
