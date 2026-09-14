# Valkey Samples

A list of curated resources with demos, tutorials and samples for Valkey.

## Cookbooks

### KV caching

- **LMCache** — [KV caching with Valkey](cookbooks/kv-caching/kv-caching-with-valkey.ipynb): cache the attention KV that vLLM computes during prefill in Valkey through LMCache, so a shared prompt prefix is reused across requests and across vLLM replicas. Runs on CPU end to end.
