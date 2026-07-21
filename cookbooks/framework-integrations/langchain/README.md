# LangChain + Valkey

> Learn the Valkey persistence, cache, and vector-store APIs used by a local LangGraph sample.

This four-page progression uses a deterministic, credential-free local default. Optional provider addenda explain where Bedrock-backed models or embeddings can fit without changing the default path.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | [Getting Started](01-getting-started.md) | Start the pinned Valkey bundle and persist LangGraph checkpoint state with `ValkeySaver`. | Beginner, about 15 minutes, Python |
| 02 | [LLM Response Caching](02-llm-caching.md) | Use `ValkeyCache` for deterministic exact-key cache reads and writes, including TTL configuration. | Intermediate, about 20 minutes, Python |
| 03 | [Semantic Search with ValkeyStore](03-semantic-search.md) | Store documents and search by meaning with deterministic embeddings and `ValkeyStore`. | Intermediate, about 20 minutes, Python |
| 04 | [Full Agent](04-full-agent.md) | Wire `ValkeySaver`, `ValkeyStore`, and `ValkeyCache` together in a help-desk flow with semantic caching and checkpointing. | Advanced, about 25 minutes, Python |

All commands and snippets are based on [`sample/main.py`](sample/main.py). The
sample does not call a hosted model by default; provider setup is optional and
is documented only as an addendum in the relevant pages.
