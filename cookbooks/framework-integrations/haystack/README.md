# Haystack with Valkey

> Build production RAG pipelines using Valkey as a high-performance vector store inside Haystack. From first connection to a full retrieval-augmented generation pipeline.

Haystack is an open-source framework maintained by [deepset](https://www.deepset.ai/) for building search and RAG applications.
The `valkey-haystack` integration exposes Valkey-backed document storage and retrieval as Haystack components.

The default sample path uses fixed vectors and needs no API key, model download, or external service. The cookbook pages show how to add Ollama embedders and generators for a complete local RAG experience.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install the Haystack-Valkey integration, connect to Valkey, store documents with embeddings, and run your first similarity search. | Beginner, ~15 min, Python |
| 02 | <nobr>[RAG Pipeline](02-rag-pipeline.md)</nobr> | Build a full retrieval-augmented generation pipeline — embed documents, store in Valkey, retrieve by similarity, and generate answers with a local LLM. | Intermediate, ~20 min, Python |
