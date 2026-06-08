# Getting Started with ChatDev + Valkey

> Use ValkeyMemory to give ChatDev agents persistent vector memory backed by Valkey Search via the valkey-glide-sync client.

**Beginner** · Python · ~15 min

ChatDev is a multi-agent workflow orchestration platform that runs LLM-powered agents collaboratively. The `ValkeyMemory` backend stores agent memories as Valkey Hashes with HNSW-indexed vector embeddings, enabling semantic retrieval across workflow runs.

## What Gets Stored

Each memory item is a Valkey Hash with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `content_summary` | TEXT | The text content of the memory |
| `embedding` | VECTOR (float32) | Embedding vector for similarity search |
| `agent_role` | TAG | The role of the agent that created the memory |
| `timestamp` | NUMERIC | Unix timestamp of creation |

Keys follow the pattern `{key_prefix}{uuid}` (default: `memory:{uuid}`).

## Prerequisites

- Docker installed
- Python 3.12+
- An LLM API key (for embeddings — e.g., OpenAI, or use a local sentence-transformers model)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and Search is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

## Step 2: Install ChatDev with Valkey Support

```bash
git clone https://github.com/OpenBMB/ChatDev.git
cd ChatDev
pip install -e ".[valkey]"
```

The `[valkey]` extra installs `valkey-glide-sync`, the official synchronous GLIDE client.

## Step 3: Configure a Workflow with Valkey Memory

Create a workflow YAML that uses the Valkey memory backend:

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

## Step 4: Run the Workflow

```bash
export API_KEY="sk-..."
export BASE_URL="https://api.openai.com/v1"

python run.py --yaml yaml_instance/demo_valkey_memory.yaml
```

On first run, ValkeyMemory will:
1. Compute a test embedding to determine the vector dimension
2. Create an FT index (`FT.CREATE`) with HNSW COSINE metric
3. Start storing and retrieving memories

## Step 5: Verify Data in Valkey

```bash
# Check the index was created
docker exec valkey valkey-cli FT.INFO chatdev_memory

# See stored memory keys
docker exec valkey valkey-cli KEYS "memory:*"

# Inspect a memory item
docker exec valkey valkey-cli HGETALL "memory:<uuid>"
```

## How It Works

```
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
```
Query text → embed(query) → FT.SEARCH index "(@agent_role:{role})=>[KNN 3 @embedding $vec]"
                    ↓
        Parse results → filter by similarity_threshold → sort by score → return MemoryItems
```

## Next Steps

- [02 - Vector Memory](02-vector-memory.md): Deep dive into retrieval, threshold tuning, and TTL
- [03 - Production](03-production.md): TLS, ACL auth, and multi-process deployment
