# Getting Started with ChatDev + Valkey

> Use ValkeyMemory to give ChatDev agents persistent vector memory backed by Valkey Search via the valkey-glide-sync client.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building or evaluating multi-agent LLM workflows who want persistent, semantically searchable agent memory backed by Valkey.

ChatDev is a multi-agent workflow orchestration platform that runs LLM-powered agents collaboratively. The `ValkeyMemory` backend
stores agent memories as Valkey Hashes with HNSW-indexed vector embeddings, enabling semantic retrieval across workflow runs.

> **Upstream status:** [ChatDev](https://github.com/OpenBMB/ChatDev) is an [OpenBMB](https://github.com/OpenBMB) open-source project.
> Its `ValkeyMemory` backend is proposed in upstream pull request [OpenBMB/ChatDev#634](https://github.com/OpenBMB/ChatDev/pull/634),
> which is **open and unmerged** at the time of writing. This cookbook and its sample code independently reproduce the verified
> Valkey behavior from that PR — they do not import ChatDev, because ChatDev's `pyproject.toml` declares `package = false` and
> cannot be installed as a library dependency. Until PR #634 is merged and published, the standalone [`sample/`](sample/)
> directory is the only runnable path described in this cookbook; Steps 2–5 below describe the proposed ChatDev
> configuration and API shape for reference against the PR, not a runnable workflow.

## What Gets Stored

Each memory item is a Valkey Hash with these fields:

| Field | Type | Description |
| --- | --- | --- |
| `content_summary` | TEXT | The text content of the memory |
| `embedding` | VECTOR (float32) | Embedding vector for similarity search |
| `agent_role` | TAG | The role of the agent that created the memory |
| `timestamp` | NUMERIC | Unix timestamp of creation |

Keys follow the pattern `{key_prefix}{uuid}` (default: `memory:{uuid}`).

## Prerequisites

- Docker or Podman installed
- Python 3.11+
- Valkey Bundle 9.1.0 (includes the Search module — plain `valkey/valkey` will not work)
- An LLM API key only if a future merged ChatDev release supports this workflow (for embeddings — e.g., OpenAI, or use
  a local sentence-transformers model). The standalone `sample/` code needs no API key.

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

Podman alternative:

```bash
podman run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> To remove an existing container on re-run: `docker rm -f valkey` (or `podman rm -f valkey`)
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/) and [03 - Production](03-production.md).

Verify it's running and Search is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

## Step 2: How ChatDev Would Wire Up Valkey Memory

This section maps the proposed `ValkeyMemory` integration from
[PR #634](https://github.com/OpenBMB/ChatDev/pull/634) to ChatDev's configuration surface, for reference
against the PR. **It is not a runnable path today** — the PR is open and unmerged, and ChatDev's
`pyproject.toml` declares `package = false`, so ChatDev cannot be installed as a library dependency
regardless of merge status. Once the PR is merged and published, the `[valkey]` extra proposed there
would install `valkey-glide-sync`, the official synchronous GLIDE client, as ChatDev's memory backend
dependency.

The proposed integration surface has two parts:

| ChatDev concept | Config field | Maps to |
| --- | --- | --- |
| Memory backend type | `memory[].type: valkey` | Selects `ValkeyMemory` as the storage implementation |
| Connection | `memory[].config.host` / `.port` | `ValkeyMemoryConfig.host` / `.port` (see `sample/valkey_memory.py`) |
| Index naming | `memory[].config.index_name` | `ValkeyMemoryConfig.index_name` — the FT index created on first use |
| Embedding provider | `memory[].config.embedding` | Selects the embedding backend (`provider`, `model`, `api_key`) |
| Per-agent retrieval | `agent.memories[].top_k`, `.retrieve_stage`, `.read`, `.write` | Controls how many results a KNN query returns and when memory is read/written |

For the exact runtime behavior these fields would drive — schema, TAG sanitization, KNN query
construction, TTL semantics — see the standalone, independently runnable [`sample/`](sample/) below and
[02 - Vector Memory](02-vector-memory.md), which exercise the same logic against real Valkey today.

## Step 3: Proposed Workflow Configuration

The YAML below illustrates the workflow shape proposed in PR #634 — how a workflow would declare an
agent with Valkey-backed memory once the integration is merged and published. It is shown for API
reference only and cannot be run against ChatDev today.

```yaml
version: 0.4.0
vars: {}
graph:
  id: ''
  description: Simple agent with Valkey-backed persistent memory.
  nodes:
    - id: assistant
      type: agent
      config:
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        provider: openai
        name: gpt-4o
        role: |
          You are a helpful assistant with persistent memory.
          Use memories from previous conversations to provide
          personalized responses.
        params:
          temperature: 0.7
          max_tokens: 2000
        memories:
          - name: chatdev_memory
            top_k: 3
            retrieve_stage:
              - gen
            read: true
            write: true
  edges: []
  memory:
    - name: chatdev_memory
      type: valkey
      config:
        host: localhost
        port: 6379
        index_name: chatdev_memory
        embedding:
          provider: openai
          model: text-embedding-3-small
          api_key: ${API_KEY}
  start:
    - assistant
  end: []
  initial_instruction: ''
```

## Step 4: What Running the Workflow Would Do

The commands below illustrate how the workflow would be launched once PR #634 is merged and published.
This step is descriptive — it cannot be run against ChatDev today.

```bash
export API_KEY="sk-..."
export BASE_URL="https://api.openai.com/v1"

python run.py --path yaml_instance/demo_valkey_memory.yaml
```

On first run, `ValkeyMemory` would:

1. Compute a test embedding to determine the vector dimension
2. Create an FT index (`FT.CREATE`) with HNSW COSINE metric
3. Start storing and retrieving memories

The standalone [`sample/`](sample/) reproduces exactly this sequence today, against real Valkey, without
needing ChatDev or an API key — run `python sample/quick_start.py` to see it live.

## Step 5: Inspecting Data in Valkey

Once memories are stored (via the standalone sample, or a future merged integration), you can inspect
them directly:

```bash
# Check the index was created
docker exec valkey valkey-cli FT.INFO chatdev_memory

# See stored memory keys
docker exec valkey valkey-cli SCAN 0 MATCH "memory:*" COUNT 100

# Inspect a memory item
docker exec valkey valkey-cli HGETALL "memory:<uuid>"
```

## Try It: The Runnable Sample

The [`sample/`](sample/) directory contains a fully standalone, runnable reimplementation
of `ValkeyMemory`'s store/retrieve/expire mechanics against real Valkey — no ChatDev
install, no API key, no network access required. This is the only runnable path in this
cookbook until PR #634 is merged and published:

```bash
cd sample
pip install -r requirements.txt
python quick_start.py
```

See [`sample/README.md`](sample/README.md) for details and expected output.

## How It Works

```text
User input → Agent generates response
                    ↓
            ValkeyMemory.update()
                    ↓
        embed(text) → float32 bytes
                    ↓
        HSET memory:{uuid} content_summary ... embedding ... agent_role ... timestamp ...
                    ↓
        EXPIRE memory:{uuid} ttl_seconds (if configured)
```

On retrieval:

```text
Query text → embed(query) → FT.SEARCH index "(@agent_role:{role})=>[KNN 3 @embedding $vec]"
                    ↓
        Parse results → filter by similarity_threshold → sort by score → return MemoryItems
```

| Component | Role |
| --- | --- |
| `valkey-glide-sync` | Synchronous Valkey client used by ValkeyMemory to talk to the server |
| Valkey Search | Provides the `FT.CREATE`/`FT.SEARCH` commands and the HNSW vector index |
| Valkey Hash | Storage format for each memory item (`content_summary`, `embedding`, `agent_role`, `timestamp`) |
| TAG field (`agent_role`) | Pre-filters KNN search to a single agent's memories |
| VECTOR field (`embedding`) | HNSW-indexed float32 vector enabling cosine-similarity KNN search |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | — | `localhost` | Valkey server address |
| `port` | — | `6379` | Valkey server port |
| `index_name` | — | `memory_index` | FT index name |
| `key_prefix` | — | `memory:` | Hash key prefix |
| `ttl_seconds` | — | `None` | Per-entry TTL in seconds (`None` = no expiry) |
| `embedding` | ✓ | — | Embedding provider config (`provider`, `model`, `api_key`) |

## Next Steps

- [02 - Vector Memory](02-vector-memory.md): Deep dive into retrieval, threshold tuning, and TTL

---

[← README](README.md) | [02 - Vector Memory →](02-vector-memory.md)
