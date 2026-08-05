# LangBot + Valkey

> 3 cookbooks for using Valkey Search as a RAG vector database in LangBot — the production-grade platform for building agentic IM bots.
> The backend is opt-in and disabled by default, and talks to Valkey through the official `valkey-glide` client.

## What is LangBot?

[LangBot](https://github.com/langbot-app/LangBot) is an open-source, production-grade platform for building agentic IM bots across
Discord, Slack, Telegram, WeChat, Lark, DingTalk, QQ, Matrix, and more. It ships agent orchestration, a knowledge base (RAG), a plugin
system, and a configurable message pipeline.

Valkey plugs into LangBot's knowledge-base subsystem as a `valkey_search` backend — it stores embeddings in Valkey Search and serves vector, full-text, and hybrid queries.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey with the search module, verify the connection with `valkey-glide`, and enable LangBot's opt-in vector-search backend. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Search](02-vector-search.md)</nobr> | Create an HNSW index, store embeddings as HASH keys, and run KNN similarity queries via the typed `ft` API. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Hybrid Search & Filtering](03-hybrid-and-filtering.md)</nobr> | Full-text and hybrid filter-then-KNN, `file_id` TAG filtering, the `vector_weight` caveat, and query-injection safety. | Advanced, ~20 min, Python |

## Runnable Sample

The [`sample/`](sample/) directory contains a self-contained script (`vector_search.py`) that exercises the integration end-to-end
against a local Valkey. See [sample/README.md](sample/README.md) to run it.
