# Vector Store RAG with Langflow and Valkey

> Ingest documents into Valkey Vector Store and build a RAG chatbot
> that answers questions using semantic similarity search.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers building Retrieval-Augmented Generation (RAG)
applications who want a visual workflow for document ingestion and retrieval,
backed by Valkey's vector search capabilities.
You should have completed the [Getting Started](01-getting-started.md) guide.

## Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Docker | 20.10+ | Run Valkey with search module |
| Python | 3.10–3.13 | Run Langflow |
| Langflow | 1.11+ | Valkey bundle included |
| OpenAI API key | — | Embeddings and LLM (or use Ollama) |

> **Security:** Never expose Valkey to the public internet without authentication.
> Use `requirepass` or ACLs in production. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Step 1: Start Valkey with Search Module

The Valkey Vector Store requires the `valkey-search` module for `FT.CREATE` and
`FT.SEARCH` commands. Use the `valkey-bundle` image:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.1
```

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# 1) 1) "name"
#    2) "search"
#    3) "ver"
#    4) ...
```

## Step 2: Create the Data Ingestion Flow

This flow loads a file, splits it into chunks, generates embeddings, and stores
everything in Valkey.

1. Click **New Flow** → **Blank Flow**.
2. Drag these components onto the canvas:
   - **File** (under Data)
   - **Split Text** (under Processing)
   - **OpenAI Embeddings** (under Embeddings) — or **Ollama Embeddings**
   - **Valkey** vector store (under Bundles → Valkey)
   - **Chat Output** (under Input/Output) — for status confirmation

3. Connect:
   - **File** → **Split Text** (data)
   - **Split Text** → **Valkey** vector store (ingest_data)
   - **OpenAI Embeddings** → **Valkey** vector store (embedding)
   - **Valkey** vector store → **Chat Output** (confirmation)

4. Configure **Split Text**:
   - Chunk size: `1000`
   - Chunk overlap: `200`
   - Separator: `\n\n`

## Step 3: Configure the Valkey Vector Store (Ingestion)

Select the **Valkey** vector store component and configure:

| Parameter | Value | Notes |
| --- | --- | --- |
| Valkey Server URL | `valkey://localhost:6379` | Connection string |
| Valkey Index Name | `langflow-docs` | Name for the vector index |
| Number of Results | `4` | Not used during ingestion |

The component automatically creates the index with `FT.CREATE` when documents
are first ingested.

## Step 4: Ingest Documents

1. Click the **File** component and upload a document (PDF, TXT, or Markdown).
2. Click the **Valkey** vector store component → **Run component**.
3. The flow processes the file: split → embed → store in Valkey.

Verify documents were stored:

```bash
docker exec valkey valkey-cli FT.INFO langflow-docs
# num_docs: <number of chunks>
```

## Step 5: Create the Retrieval Flow

Now build a separate flow (or add to the same canvas) for answering questions:

1. Drag these components:
   - **Chat Input** (under Input/Output)
   - **OpenAI Embeddings** (under Embeddings) — same model as ingestion
   - **Valkey** vector store (under Bundles → Valkey)
   - **Parser** (under Processing)
   - **Prompt** (under Prompts)
   - **OpenAI** model (under Models)
   - **Chat Output** (under Input/Output)

2. Connect:
   - **Chat Input** → **Valkey** vector store (search_query)
   - **OpenAI Embeddings** → **Valkey** vector store (embedding)
   - **Valkey** vector store → **Parser** (search results)
   - **Parser** → **Prompt** (context)
   - **Chat Input** → **Prompt** (question)
   - **Prompt** → **OpenAI** model (input)
   - **OpenAI** model → **Chat Output** (response)

3. Configure the **Prompt** template:

```text
Answer the question based only on the following context.
If the context doesn't contain the answer, say "I don't have that information."

Context:
{context}

Question: {question}

Answer:
```

## Step 6: Configure the Valkey Vector Store (Retrieval)

Use the same index name as ingestion:

| Parameter | Value | Notes |
| --- | --- | --- |
| Valkey Server URL | `valkey://localhost:6379` | Same server |
| Valkey Index Name | `langflow-docs` | Must match ingestion index |
| Number of Results | `4` | Top-K results to retrieve |

## Step 7: Test the RAG Pipeline

1. Open the **Playground**.
2. Ask a question about your uploaded document.
3. The flow retrieves relevant chunks from Valkey and generates an answer.

## Using Ollama Instead of OpenAI

For a fully local setup (no API keys needed):

1. Install and run [Ollama](https://ollama.ai/) with an embedding model:

   ```bash
   ollama pull nomic-embed-text
   ollama pull llama3.2
   ```

2. Replace **OpenAI Embeddings** with **Ollama Embeddings**:
   - Model: `nomic-embed-text`
   - Base URL: `http://localhost:11434`

3. Replace the **OpenAI** model with **Ollama**:
   - Model: `llama3.2`
   - Base URL: `http://localhost:11434`

4. Update the vector store schema dimensions if needed. The default schema uses
   1536 dimensions (OpenAI). For `nomic-embed-text`, set the vector schema to 768
   dimensions via the component's advanced settings.

## How It Works

The Valkey Vector Store component wraps `langchain-aws`'s `ValkeyVectorStore` class,
which uses `valkey-glide` to communicate with the server.

```text
Ingestion:
┌──────┐    ┌────────────┐    ┌────────────┐    ┌─────────────────┐
│ File │───▶│ Split Text │───▶│ Embeddings │───▶│ Valkey Vector   │
└──────┘    └────────────┘    └────────────┘    │ Store (ingest)  │
                                                └─────────────────┘

Retrieval:
┌────────────┐    ┌─────────────────┐    ┌────────┐    ┌─────┐
│ Chat Input │───▶│ Valkey Vector   │───▶│ Parser │───▶│ LLM │
└────────────┘    │ Store (search)  │    └────────┘    └──┬──┘
                  └─────────────────┘                     │
                                                          ▼
                                                   ┌─────────────┐
                                                   │ Chat Output │
                                                   └─────────────┘
```

Valkey commands used:

- **Ingestion:** `FT.CREATE` (index), `HSET` (documents with vectors)
- **Search:** `FT.SEARCH` with `KNN` clause for similarity

## Configuration Reference

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| valkey_server_url | SecretString | _(required)_ | Connection URL (`valkey://host:port`) |
| valkey_index_name | String | _(required)_ | Vector index name |
| ingest_data | Data | _(optional)_ | Documents to store |
| search_query | String | _(optional)_ | Query for similarity search |
| embedding | Embeddings | _(required)_ | Embedding model instance |
| number_of_results | Integer | `4` | Number of search results (top-K) |
| should_cache_vector_store | Boolean | `true` | Cache store instance across outputs |

## Troubleshooting

**"Module 'search' not loaded" error:**

You're using `valkey/valkey` instead of `valkey/valkey-bundle`.
Stop the container and restart with:

```bash
docker rm -f valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.1
```

**Embeddings dimension mismatch:**

If you switch embedding models, drop the old index first:

```bash
docker exec valkey valkey-cli FT.DROPINDEX langflow-docs DD
```

The `DD` flag also deletes the underlying documents.

**No results returned:**

Verify documents exist in the index:

```bash
docker exec valkey valkey-cli FT.INFO langflow-docs
```

Check that the search query embedding model matches the ingestion embedding model.

---

| | |
| --- | --- |
| [← Getting Started](01-getting-started.md) | [Programmatic API →](03-programmatic-api.md) |
