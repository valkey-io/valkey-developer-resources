# Valkey Developer Resources

A list of curated resources with demos, tutorials, samples and recipes for Valkey.

## Cookbook

This cookbook is a set of recipes — runnable, notebook-based walkthroughs of a
Valkey usage pattern.

### KV caching

Cache the attention KV an LLM computes for a shared prompt prefix so it is reused across requests and instances instead of recomputed.

- **LMCache** — [KV caching with Valkey](cookbooks/kv-caching/): set up KV caching on CPU, verify shared-prefix reuse across requests and vLLM replicas, and see its effect on inference latency. Start with the cookbook README, then run the notebook.

### LLM serving

Route requests across several vLLM servers by what each one has cached, and queue batch work, with Valkey holding the shared state.

- **llm-d** — [llm-d serving with Valkey](cookbooks/llm-d-serving/): put llm-d's router in front of the KV caching recipe's two CPU vLLM servers and use one Valkey for the router's prefix-cache index, the shared KV cache, and llm-d-async's batch queue and per-user quotas. Start with the recipe README, then run the notebook.
