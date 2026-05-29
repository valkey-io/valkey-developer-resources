# Getting Started with Kilocode + Valkey

> Select Valkey as your vector store backend and get semantic code search in under 10 minutes.

**Beginner** · Kilocode · ~10 min

## Kilocode in 30 seconds

[Kilocode](https://github.com/Kilo-Org/kilocode) is an open-source AI coding agent (VS Code extension + CLI). It generates code from natural language, automates refactoring, and runs terminal commands. Supports 500+ AI models.

Its Codebase Indexing feature parses your project with Tree-sitter, generates embeddings for each semantic code block, and stores vectors in a vector database for similarity search. The agent finds relevant code by meaning, not by matching text.

Kilocode supports three vector store backends: Qdrant, LanceDB, and Valkey. With Valkey you get a single in-memory store that handles both vector indexing and similarity search via ValkeySearch's HNSW algorithm. No separate vector database required.

## Prerequisites

- Docker installed (for Valkey)
- VS Code or the Kilocode CLI (`npm install -g @kilocode/cli`)

## Step 1: Start Valkey

Kilocode requires Valkey 8.1.1+ with the ValkeySearch module. Use `valkey/valkey-bundle` which includes it:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should include: name search
```

## Step 2: Install Kilocode

**VS Code:** Install from the Marketplace (search `kilocode.kilo-code`) or visit the [extension page](https://marketplace.visualstudio.com/items?itemName=kilocode.kilo-code).

**CLI:**

```bash
npm install -g @kilocode/cli
```

## Step 3: Configure Valkey as the Vector Store

**VS Code:**

1. Open Kilo Code Settings → **Experimental** → toggle **Semantic Indexing** on.
2. Open Settings → **Indexing** → toggle **Enable Indexing** on.
3. Pick an **Embedding Provider** (e.g., OpenAI with `text-embedding-3-small`).
4. Set **Vector Store** to **"Valkey"**.
5. Enter your **Valkey URL** (`redis://localhost:6379`) and optionally a password.

That's it. No schema setup, no index creation. Kilocode does the rest.

**CLI:**

Edit `kilo.jsonc` directly (located in your XDG config directory or `.kilo/` in your project):

```jsonc
{
  "experimental": { "semantic_indexing": true },
  "indexing": {
    "enabled": true,
    "provider": "openai",
    "model": "text-embedding-3-small",
    "vectorStore": "valkey",
    "openai": { "apiKey": "sk-..." },
    "valkey": {
      "url": "redis://localhost:6379"
    }
  }
}
```

> **Note:** Never commit real API keys to version control. Use environment variables or add your config file to `.gitignore`.

## Step 4: Index Your Project

Open a project in VS Code (or navigate to one in the CLI). Kilocode begins indexing automatically. Progress shows in the status bar:

```
IDX 24% 142/580
IDX 100% 580/580
IDX Complete
```

The indexer:
1. Splits source files into semantic chunks using Tree-sitter
2. Generates embeddings for each chunk
3. Stores vectors in Valkey as HNSW indexes

## Step 5: Search Your Codebase

Use Kilocode's semantic search to find code by meaning:

```
> Search: "function that validates user email"

Results:
  src/validators/email.ts:12    validateEmail(input: string): boolean
  src/auth/signup.ts:45         checkEmailFormat(email: string)
  src/utils/validation.ts:8     isValidEmailDomain(domain: string)
```

Results are ranked by vector similarity. Your query doesn't need to match function names exactly.

## Step 6: Verify in Valkey

You can confirm the index was created directly in Valkey:

```bash
# List all FT indexes. Kilocode creates indexes named ws-<hash>
docker exec valkey valkey-cli FT._LIST

# Inspect the index (replace with your actual index name from FT._LIST)
docker exec valkey valkey-cli FT.INFO ws-a1b2c3d4e5f67890
```

You'll see the HNSW index with vector and TAG fields, all created automatically.

## Under the hood

Kilocode's `kilo-indexing` package uses `@valkey/valkey-glide` to:

1. Connect to your Valkey instance
2. Create a ValkeySearch index (HNSW, COSINE, FLOAT32) with TAG fields for path filtering
3. Batch-upsert code chunk embeddings via GLIDE pipelines (non-atomic `Batch`)
4. Run KNN queries with directory-scoped TAG filters

The collection name is derived from a SHA-256 hash of your workspace path (e.g., `ws-a1b2c3d4e5f67890`), so different projects get separate indexes without conflicts.

The next cookbook covers what's stored in Valkey and how the search works.

---

[02 - How It Works →](02-how-it-works.md)
