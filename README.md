# Valkey Developer Resources

A list of curated resources with demos, tutorials, samples and recipes for Valkey.

## Cookbook

This cookbook is a set of recipes — runnable, notebook-based walkthroughs of a
Valkey usage pattern.

### KV caching

Cache the attention KV an LLM computes for a shared prompt prefix so it is reused across requests and instances instead of recomputed.

- **LMCache** — [KV caching with Valkey](cookbooks/kv-caching/): set up KV caching on CPU, verify shared-prefix reuse across requests and vLLM replicas, and see its effect on inference latency. Start with the cookbook README, then run the notebook.

### Queue and quota

Use a Valkey sorted set as both a priority job queue and a sliding-window admission quota, one data structure doing two separate jobs at once.

- **llm-d** — [Queue and quota with Valkey](cookbooks/queue-and-quota/): point llm-d's async batch processor at Valkey, submit inference jobs, watch them queue in priority order and drain, then send a burst past a per-user quota and watch the gate refuse the overflow. Start with the cookbook README, then run the notebook.
