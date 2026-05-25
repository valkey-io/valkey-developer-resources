# Genkit + Valkey

> 3 cookbooks for using Valkey as the vector store backing a Genkit AI application - indexing documents, retrieving by meaning, and filtering by metadata. All cookbooks include code examples for TypeScript, Python, and Go.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install the Valkey plugin, connect to Valkey, and index your first documents with HNSW vector embeddings. | Beginner, ~15 min, TypeScript/Python/Go |
| 02 | <nobr>[Retrieval-Augmented Generation](02-rag.md)</nobr> | Build a RAG pipeline that retrieves relevant documents from Valkey and injects them into a grounded LLM prompt. | Intermediate, ~20 min, TypeScript/Python/Go |
| 03 | <nobr>[Metadata Filtering](03-metadata-filtering.md)</nobr> | Add TAG and NUMERIC metadata fields to narrow vector search results with pre-filters before KNN kicks in. | Intermediate, ~20 min, TypeScript/Python/Go |
