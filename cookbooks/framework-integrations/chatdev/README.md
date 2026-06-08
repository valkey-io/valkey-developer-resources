# ChatDev + Valkey

> 3 cookbooks for using Valkey as the persistent vector memory backend for ChatDev multi-agent workflows — session memory, HNSW-indexed retrieval, and production deployment via the valkey-glide-sync client.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install ChatDev with Valkey support, connect to Valkey, and run a workflow with persistent agent memory. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Memory](02-vector-memory.md)</nobr> | Use `ValkeyMemory` to store and retrieve agent memories with HNSW vector search, threshold filtering, and TTL expiry. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production](03-production.md)</nobr> | Configure TLS encryption, ACL authentication, TTL policies, and multi-process deployments. | Advanced, ~15 min, Python |
