# OpenAI + Valkey

> Use Valkey Search with OpenAI embeddings for JSON vector search, hybrid filtering, and FLAT versus HNSW indexes through `valkey-glide`.

**Who is this for:** Python developers adding semantic search to an application that already uses Valkey and can optionally provide OpenAI embeddings.

## What is OpenAI + Valkey?

[OpenAI embeddings](https://platform.openai.com/docs/guides/embeddings) turn
text into dense vectors that capture meaning. [Valkey
Search](https://valkey.io/topics/search/) is an open-source Valkey module that
adds native vector similarity search and secondary indexing.

Together they let you build semantic search and RAG workloads in Valkey: embed
your text, store and index the vectors, and query by meaning. The sample uses
deterministic local vectors by default so its Valkey path runs without
credentials; set `OPENAI_API_KEY` to exercise OpenAI embeddings.

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- No credentials for the default sample path
- An OpenAI API key only for the optional provider path

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect to Valkey, create a JSON vector index, store documents, and run your first KNN vector search with OpenAI embeddings. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Search](02-vector-search.md)</nobr> | Hybrid search combining a TAG pre-filter with KNN, plus the HNSW index for fast approximate search on larger datasets. | Intermediate, ~20 min, Python |
