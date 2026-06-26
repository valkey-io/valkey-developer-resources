# LangChain4j + Valkey

> 4 cookbooks for using Valkey as a vector embedding store in Java applications with LangChain4j — semantic search, metadata filtering, and RAG pipelines powered by the official `langchain4j-community-valkey` package.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Add the Maven dependency, connect to Valkey with GlideClient, store embeddings, and run your first similarity search. | Beginner, ~15 min, Java |
| 02 | <nobr>[Metadata Filtering](02-metadata-filtering.md)</nobr> | Index documents with typed metadata (TAG, NUMERIC, TEXT), then combine vector similarity with metadata filters for precise retrieval. | Intermediate, ~20 min, Java |
| 03 | <nobr>[RAG Pipeline](03-rag-pipeline.md)</nobr> | Build end-to-end Retrieval-Augmented Generation: chunk documents, embed with Amazon Bedrock Titan, store in Valkey, and answer questions with Claude. | Intermediate, ~25 min, Java |
| 04 | <nobr>[Production Patterns](04-production.md)</nobr> | HNSW vs FLAT indexing, distance metrics, batch ingestion, connection management, error handling, and scaling. | Advanced, ~20 min, Java |
