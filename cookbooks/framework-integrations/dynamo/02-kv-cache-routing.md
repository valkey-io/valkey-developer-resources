# KV-Aware Routing with Valkey

> Leverage Dynamo's KV router to direct requests toward workers with warm caches, minimizing redundant prefill across the cluster.

**Intermediate** · Python · ~20 min

Dynamo's KV router doesn't just load-balance — it tracks which KV cache blocks exist on which workers and routes requests to maximize cache hits. When Valkey backs the L2 layer through LMCache, cache blocks are available cluster-wide, and the router places requests where the most prefix overlap exists.

## How KV-Aware Routing Works

```
Request: "Explain transformers..."
  │
  ▼
┌──────────────────────────────────────────────┐
│              Dynamo KV Router                 │
│                                              │
│  1. Hash prompt tokens into blocks           │
│  2. Query index: which workers have overlap? │
│  3. Score: prefill_cost vs decode_cost       │
│  4. Route to worker with lowest total cost   │
└──────────────────────────────────────────────┘
  │
  ▼ routed to Worker with highest overlap
┌─────────────┐
│  Worker 1   │ → L1 hit (local CPU) or L2 hit (Valkey)
│  +LMCache   │ → skip prefill, decode immediately
└─────────────┘
```

The router evaluates per-worker cost as a combination of:
- **Decode cost**: active blocks / inflight requests on the worker
- **Prefill cost**: new tokens that must be computed (not cached)
- **KV cache overlap**: how many tokens are already cached on that worker

## Step 1: Enable the KV Router

Launch the frontend with `--router-mode kv`:

```bash
python3 -m dynamo.frontend \
  --discovery-backend file \
  --router-mode kv \
  --http-port 8000
```

That's it. The `kv` routing mode enables prefix-aware, cache-conscious routing. Workers automatically publish KV cache events to the router's indexer.

### CLI Arguments for Router Tuning

| Argument | Default | Description |
|----------|---------|-------------|
| `--router-mode kv` | `round-robin` | Enable KV cache-aware routing |
| `--router-temperature <f>` | `0.0` | Routing randomness (0.0 = deterministic) |
| `--kv-cache-block-size <n>` | Backend-specific | Block size (match your backend config) |
| `--no-router-kv-events` | events enabled | Disable real-time KV event tracking (approximate mode) |
| `--load-aware` | disabled | Route by active load without cache signals |
| `--router-queue-policy <p>` | `fcfs` | Queue scheduling: `fcfs`, `wspt`, or `lcfs` |

All CLI arguments can also be set as environment variables with the `DYN_` prefix (e.g., `DYN_ROUTER_MODE=kv`).

## Step 2: Launch Workers with KV Event Publishing

Workers must publish KV cache events so the router knows what's cached where. This happens automatically when using LMCache with the `LMCacheMPConnector`:

```bash
# Start LMCache sidecar (per worker)
lmcache server \
  --l1-size-gb 5 \
  --eviction-policy LRU \
  --l2-adapter '{"type": "resp", "host": "localhost", "port": 6379}' \
  --chunk-size 256 &

# Start worker
python3 -m dynamo.vllm \
  --model Qwen/Qwen3-0.6B \
  --discovery-backend file \
  --disable-hybrid-kv-cache-manager \
  --kv-transfer-config '{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both"}'
```

Repeat for additional workers (each on a separate GPU via `CUDA_VISIBLE_DEVICES`).

## Step 3: Observe Routing in Action

Send multiple requests with shared prefixes:

```bash
# Request 1: full prompt (cold)
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is attention?"}
    ],
    "max_tokens": 50
  }'

# Request 2: same system prompt, different user query
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is backpropagation?"}
    ],
    "max_tokens": 50
  }'
```

Both share the system prompt prefix. The router will route Request 2 to the worker that cached the system prompt from Request 1 — skipping that portion of prefill.

## Step 4: Monitor Router Metrics

Dynamo exposes Prometheus metrics on the frontend's HTTP port:

```bash
curl -s http://localhost:8000/metrics | grep -i router
```

The LMCache sidecar also exposes its own metrics (default port 8080):

```bash
curl -s http://localhost:8080/metrics | grep '^lmcache_mp_'
```

## The WORM Access Pattern

Agentic inference exhibits a Write-Once-Read-Many (WORM) pattern:
- System prompts and growing conversation prefixes are computed once
- Subsequent turns reuse the cached prefix

NVIDIA's benchmarks show an [11.7× read/write ratio](https://developer.nvidia.com/blog/full-stack-optimizations-for-agentic-inference-with-nvidia-dynamo/) for agentic workloads. With Valkey as L2, this cached prefix is available cluster-wide. The KV router ensures requests land on workers that already have the prefix warm.

## KV Event Transport Modes

The router can receive cache state information in different ways:

| Event Mode | How to Enable | Description |
|------------|---------------|-------------|
| NATS Core (default) | No extra flags | Workers publish events via NATS; router maintains local indexer |
| Approximate | `--no-router-kv-events` | No events; router predicts cache state from its own routing decisions |
| ZMQ | `--event-plane zmq` | Workers publish via ZMQ PUB sockets |

For single-node development, the default (NATS Core) works out of the box.

## Routing Mode Comparison

| Mode | Best For | Cache Utilization |
|------|----------|-------------------|
| `round-robin` | Even load distribution | None (ignores cache) |
| `random` | Stateless balancing | None |
| `least-loaded` | Prevent hotspots | None |
| `kv` | Multi-turn / shared prefixes | High (prefix-aware + load-aware) |

Use `--router-mode kv` whenever Valkey is configured as L2 — it's the mode that maximizes the benefit of shared remote caching.

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
