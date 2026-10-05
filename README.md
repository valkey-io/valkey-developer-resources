# Valkey Samples

A list of curated resources with demos, tutorials, samples and recipes for Valkey.

## Cookbooks

Each cookbook is a set of recipes — runnable, notebook-based walkthroughs of a
Valkey usage pattern.

### KV caching

Cache the attention KV an LLM computes for a shared prompt prefix so it is reused across requests and instances instead of recomputed.

- **LMCache** — [KV caching with Valkey](cookbooks/kv-caching/): set up KV caching on CPU, verify shared-prefix reuse across requests and vLLM replicas, and see its effect on inference latency. Start with the cookbook README, then run the notebook.
