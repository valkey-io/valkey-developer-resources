# ChatDev + Valkey

> 3 cookbooks for using Valkey as the persistent vector memory backend for ChatDev multi-agent workflows — session
> memory, HNSW-indexed retrieval, and production deployment via the valkey-glide-sync client.

## What is ChatDev?

[ChatDev](https://github.com/OpenBMB/ChatDev) is a multi-agent workflow orchestration platform that runs LLM-powered
agents collaboratively. The `ValkeyMemory` backend provides persistent vector memory via `valkey-glide-sync`.

ChatDev is an [OpenBMB](https://github.com/OpenBMB) open-source project.

## Upstream Status

The `ValkeyMemory` backend is proposed in upstream pull request [OpenBMB/ChatDev#634](https://github.com/OpenBMB/ChatDev/pull/634),
which is **open and unmerged** at the time of writing. These cookbooks describe the design from that PR, and the
[`sample/`](01-getting-started.md#try-it-the-runnable-sample) code under `01-getting-started.md`'s companion
directory independently reproduces its verified Valkey behavior (schema, sanitization, KNN queries, TTL semantics)
without importing ChatDev as a dependency — ChatDev's `pyproject.toml` declares `package = false`, so it cannot be
installed as a library. If PR #634 changes before merging, the exact schema or config field names in these cookbooks
may need to be revisited against the merged version.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Map the proposed ChatDev + Valkey configuration, then run the standalone sample for persistent agent memory. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Memory](02-vector-memory.md)</nobr> | Use `ValkeyMemory` to store and retrieve agent memories with HNSW vector search, threshold filtering, and TTL expiry. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production](03-production.md)</nobr> | Configure TLS encryption, ACL authentication, TTL policies, and multi-process deployments. | Advanced, ~15 min, Python |
