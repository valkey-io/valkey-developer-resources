# Portkey AI Gateway + Valkey

> 3 cookbooks for using Valkey as the LLM response cache and vector search backend in the Portkey AI Gateway via `@valkey/valkey-glide`.

## What is Portkey AI Gateway + Valkey?

[Portkey AI Gateway](https://github.com/Portkey-AI/gateway) is an open-source gateway that routes requests to 250+ LLMs through a single API. By default it uses an in-memory cache that is lost on restart. With [Valkey](https://valkey.io/) as the backend, the gateway gains:

* **Persistent LLM response cache** — shared across gateway instances, survives restarts
* **Native vector search** — create HNSW indexes, upsert embeddings, and run KNN queries via REST

The integration uses the official [`@valkey/valkey-glide`](https://github.com/valkey-io/valkey-glide) TypeScript client.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure the gateway to cache LLM responses in Valkey using the Portkey SDK, replacing the in-memory default. | Beginner, ~15 min, Python/TS |
| 02 | <nobr>[Vector Search](02-vector-search.md)</nobr> | Use the Portkey SDK with the `valkey-search` provider to create indexes, upsert embeddings, and run KNN queries. | Intermediate, ~20 min, Python/TS |
| 03 | <nobr>[Production with ElastiCache](03-production.md)</nobr> | Connect to ElastiCache for Valkey with TLS, cluster mode, auth, TTL tuning, and SDK error handling. | Advanced, ~20 min, Python/TS |
