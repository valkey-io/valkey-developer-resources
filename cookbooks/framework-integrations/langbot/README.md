# LangBot + Valkey

> 4 cookbooks for using Valkey as a distributed rate-limit store and a RAG vector database in LangBot — the production-grade platform for building agentic IM bots. Both backends are opt-in and disabled by default, and talk to Valkey through the official `valkey-glide` client.

## What is LangBot?

[LangBot](https://github.com/langbot-app/LangBot) is an open-source, production-grade platform for building agentic IM bots across Discord, Slack, Telegram, WeChat, Lark, DingTalk, QQ, Matrix, and more. It ships agent orchestration, a knowledge base (RAG), a plugin system, and a configurable message pipeline.

Valkey plugs into two LangBot subsystems:

- **Distributed rate limiting** — a `valkey_fixwin` pipeline algorithm that shares one fixed-window counter across multiple worker processes, replacing the per-worker in-memory limiter.
- **Vector search** — a `valkey_search` knowledge-base backend that stores embeddings in Valkey Search and serves vector, full-text, and hybrid queries.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey with the search module, verify the connection with `valkey-glide`, and enable LangBot's opt-in Valkey backends. | Beginner, ~15 min, Python |
| 02 | <nobr>[Distributed Rate Limiting](02-distributed-rate-limiting.md)</nobr> | Share a fixed-window rate-limit counter across workers with an atomic `INCR` + `EXPIRE` Lua script and a fail-open posture. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Vector Search](03-vector-search.md)</nobr> | Create an HNSW index, store embeddings as HASH keys, and run KNN similarity queries via the typed `ft` API. | Intermediate, ~20 min, Python |
| 04 | <nobr>[Hybrid Search & Filtering](04-hybrid-and-filtering.md)</nobr> | Full-text and hybrid filter-then-KNN, `file_id` TAG filtering, the `vector_weight` caveat, and query-injection safety. | Advanced, ~20 min, Python |

## Runnable Sample

The [`sample/`](sample/) directory contains two self-contained scripts (`rate_limiter.py` and `vector_search.py`) that exercise both integrations end-to-end against a local Valkey. See [sample/README.md](sample/README.md) to run them.
