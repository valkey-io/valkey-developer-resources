# CrewAI + Valkey

> 3 cookbooks for giving CrewAI agents persistent, searchable memory backed by Valkey. Custom ValkeyStorage backend with GLIDE client, vector search, and Amazon Bedrock embeddings.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Set up Valkey with Docker, install GLIDE, configure connection parameters, and verify connectivity. | Beginner, ~15 min, Python |
| 02 | <nobr>[Memory Storage Backend](02-memory-storage.md)</nobr> | Build `ValkeyStorage` - a custom CrewAI storage backend with JSON serialization, HNSW vector index, and semantic recall. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Agent Memory in Action](03-agent-memory.md)</nobr> | Wire `ValkeyStorage` into CrewAI `Memory` with Bedrock embeddings. Run agents that store and recall knowledge across executions. | Intermediate, ~20 min, Python |

