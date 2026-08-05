# Getting Started with Open WebUI and Valkey

> Set up Open WebUI with Valkey as the vector database backend for RAG in under
> 10 minutes — upload documents and ask questions grounded in your own data.

**Beginner** · Docker · ~10 min

**Who is this for:** Developers and teams deploying Open WebUI who want a fast,
self-hosted vector database for document retrieval without external dependencies
like Chroma, Milvus, or Qdrant.

## Prerequisites

- Docker and Docker Compose
- An LLM backend (Ollama recommended for local, or an OpenAI API key)

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Step 1: Create the Docker Compose File

```yaml
# docker-compose.yml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    container_name: open-webui-valkey
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - valkey-data:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  open-webui:
    image: ghcr.io/open-webui/open-webui:0.11.0
    container_name: open-webui
    ports:
      - "127.0.0.1:3000:8080"
    environment:
      - VECTOR_DB=valkey
      - VALKEY_URL=valkey://valkey:6379
    volumes:
      - open-webui-data:/app/backend/data
    depends_on:
      valkey:
        condition: service_healthy

volumes:
  valkey-data:
  open-webui-data:
```

## Step 2: Start the Services

```bash
docker compose up -d
```

Verify everything is running:

```bash
docker compose ps
```

You should see both `open-webui-valkey` (healthy) and `open-webui` (running).

## Step 3: Verify Valkey Search Module

```bash
docker exec open-webui-valkey valkey-cli MODULE LIST
```

Look for `name: search` in the output. The `valkey-bundle` image includes the search
module by default.

## Step 4: Configure Your LLM

Open <http://localhost:3000> in your browser and complete the initial setup:

1. Create an admin account
2. Go to **Admin Panel** → **Settings** → **Connections**
3. Configure your LLM backend:
   - **Ollama (recommended):** Set URL to `http://host.docker.internal:11434` (if Ollama runs on host)

<details>
<summary>Optional: Using OpenAI instead of Ollama</summary>

If you prefer a hosted LLM, add your OpenAI API key under **Admin Panel** → **Settings** → **Connections** → **OpenAI**.

This requires a paid API key and sends your prompts (including RAG context) to OpenAI's servers.

</details>

## Step 5: Upload a Document

1. Go to **Workspace** → **Knowledge** → **Create Knowledge Base**
2. Name it (e.g., "Project Docs")
3. Click **Upload Files** and add a PDF, markdown, or text file
4. Open WebUI will automatically:
   - Split the document into chunks
   - Generate embeddings (using your configured model)
   - Store chunks + vectors in Valkey via `HSET` + `FT.CREATE`

## Step 6: Ask Questions

1. Start a new chat
2. Attach the knowledge base (click the `+` icon → select your KB)
3. Ask a question — Open WebUI performs:
   - Embed your query
   - KNN search against Valkey (`FT.SEARCH *=>[KNN k @vector $query_vec]`)
   - Inject top-K results as context to the LLM
   - Return a grounded answer

## How It Works

```text
┌────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Browser   │────▶│  Open WebUI  │────▶│      Valkey      │
│            │     │  (FastAPI)   │     │  (valkey-bundle) │
└────────────┘     └──────────────┘     └──────────────────┘
                          │                       │
                   embed + search           FT.SEARCH KNN
                   via GLIDE client         on HNSW index
                          │                       │
                   ┌──────▼──────┐         ┌──────▼──────┐
                   │  LLM (Ollama│         │  HASH docs  │
                   │  / OpenAI)  │         │  + vectors  │
                   └─────────────┘         └─────────────┘
```

1. Documents are chunked and embedded on upload
2. Each chunk → `HSET {prefix}:{collection}:{id}` with vector bytes + text + metadata
3. `FT.CREATE` builds HNSW index on the `vector` field (auto-created on first insert)
4. Queries embed the question, then `FT.SEARCH` runs KNN against the index
5. Top-K results are passed to the LLM as context

## Verify Data in Valkey

Check that documents are being stored:

```bash
# List indices
docker exec open-webui-valkey valkey-cli FT._LIST

# Check a specific index
docker exec open-webui-valkey valkey-cli FT.INFO idx:open_webui:<collection-name>

# Count documents
docker exec open-webui-valkey valkey-cli FT.SEARCH idx:open_webui:<collection-name> "*" LIMIT 0 0
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VECTOR_DB` | `chroma` | Set to `valkey` to use Valkey backend |
| `VALKEY_URL` | (required) | Connection URL, e.g., `valkey://localhost:6379` |
| `VALKEY_COLLECTION_PREFIX` | `open_webui` | Key prefix for all collections |
| `VALKEY_INDEX_TYPE` | `HNSW` | Vector index algorithm (`HNSW` or `FLAT`) |
| `VALKEY_DISTANCE_METRIC` | `COSINE` | Distance metric (`COSINE`, `L2`, `IP`) |
| `VALKEY_HNSW_M` | `16` | HNSW graph connectivity |
| `VALKEY_HNSW_EF_CONSTRUCTION` | `200` | HNSW build-time search width |
| `VALKEY_HNSW_EF_RUNTIME` | `10` | HNSW query-time search width |

## Troubleshooting

### Open WebUI fails to start with "search module not loaded"

Ensure you're using `valkey/valkey-bundle` (not plain `valkey/valkey`). The bundle
image includes valkey-search.

### "Valkey core X.Y.Z is below the minimum required version"

Open WebUI requires Valkey 9.0.1+ with valkey-search 1.2.0+. Use
`valkey/valkey-bundle:9.1.0` or later.

### Documents upload but search returns nothing

- Check the index exists: `docker exec open-webui-valkey valkey-cli FT._LIST`
- Verify documents: `docker exec open-webui-valkey valkey-cli KEYS "open_webui:*" | head`
- The embedding model must be configured — check **Admin** → **Settings** → **Documents**

### Connection refused

Ensure the `VALKEY_URL` matches the service name in docker-compose. Inside Docker
networks, use the service name (`valkey://valkey:6379`), not `localhost`.

---

[→ Next: RAG Configuration](02-rag-configuration.md) · [← Back to README](README.md)
