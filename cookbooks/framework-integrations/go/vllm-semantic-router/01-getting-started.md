# vLLM Semantic Router Semantic Cache with Valkey

> Run a request through vLLM Semantic Router and let its Valkey backend serve the second matching request from cache.

**Beginner** · Go · ~20 min

**Who is this for:** Engineers who operate vLLM Semantic Router and want a supported Valkey semantic-cache backend.

## Prerequisites

- Go 1.24+
- Docker
- Python 3.10–3.12 and `pip`
- A Hugging Face access token if the embedding model download is gated
- A reachable OpenAI-compatible upstream model for `demo-model`

## Step 1: Start Valkey

```bash
docker run -d --name valkey-search -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.2
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

The bundle image includes the Search module required by the Router's Valkey backends.

## Step 2: Configure Semantic Router

Install the released CLI and validate the supplied version-specific configuration.

```bash
cd sample
python -m pip install "vllm-sr==0.3.0"
vllm-sr validate
```

`config.yaml` selects `global.stores.semantic_cache.backend_type: valkey`. Its `host` is
`host.docker.internal` because `vllm-sr serve` runs the Router in a container while Valkey is published only on the
local host. Docker Desktop resolves that hostname automatically. On native Linux, replace it with the host gateway
address supported by your container runtime before starting the Router.

## Step 3: Start Semantic Router

Point `upstream-model` in `config.yaml` at your OpenAI-compatible model, then start the supported Router service.

```bash
HF_TOKEN=hf_your_token vllm-sr serve --config config.yaml
```

The Router creates and uses the Valkey index itself. Do not create the index or send `FT.*` commands from this sample.

## Step 4: Run the Go client

In a second terminal:

```bash
cd sample
export SEMANTIC_ROUTER_URL=http://localhost:8888
export SEMANTIC_ROUTER_MODEL=demo-model
go run .
```

The first request is forwarded through Semantic Router. Cache writes are asynchronous, so the sample makes up to four
subsequent identical requests with one-to-four-second backoff until it reports `second request cache hit: true`. The
sample reads that result from the Router's documented `x-vsr-cache-hit` response header. Router logs provide the
complementary proof that it connected to Valkey and initialized the configured cache.

## How It Works

| Component | Role |
| --- | --- |
| Go sample | Sends OpenAI-compatible chat-completion requests to the Router. |
| vLLM Semantic Router | Computes cache behavior, calls the configured backend, and returns `x-vsr-cache-hit`. |
| Valkey | Persists the Router-managed semantic-cache entries and vector index. |

## Configuration Reference

| Field | Required | Value in sample | Description |
| --- | --- | --- | --- |
| `backend_type` | ✓ | `valkey` | Selects the Valkey semantic-cache backend. |
| `connection.host` | ✓ | `host.docker.internal` | Valkey endpoint visible from the Router container. |
| `similarity_threshold` | ✓ | `0.85` | Minimum similarity for a semantic cache hit. |
| `ttl_seconds` | ✓ | `3600` | Cache-entry lifetime in seconds. |
| `embedding_model` | ✓ | `bert` | Router embedding model used for cache comparisons. |
| `index.vector_field.dimension` | ✓ | `384` | Dimension for the configured BERT embeddings. |

## Step 5: Stop services

```bash
vllm-sr stop
docker rm -f valkey-search
```

---

[02 - Vector Store Configuration →](02-vector-store.md)
