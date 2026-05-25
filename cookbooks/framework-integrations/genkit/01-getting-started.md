# Getting Started with Genkit + Valkey

**Beginner** · TypeScript · Python · Go · ~15 min

## What is Genkit + Valkey?

Genkit is Google's open-source framework for building production AI applications with type-safe flows, built-in tracing, and a rich plugin ecosystem. The problem: vector search requires a fast, persistent store that can survive restarts and scale independently of your application. Valkey backs the official Genkit Valkey plugin and handles all indexing and retrieval.

[Genkit](https://github.com/firebase/genkit) treats retrievers and indexers as first-class primitives:

  * **Sub-millisecond retrieval** - HNSW KNN search in ~0.5ms
  * **Persistent across restarts** - documents survive server restarts without re-indexing
  * **Type-safe flows** - schema-validated inputs and outputs throughout
  * **Drop-in retriever** - swap any other vector store for Valkey with one line

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes the Search module needed for HNSW vector indexing. Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
docker exec valkey valkey-cli MODULE LIST
# ... search module listed
```

## Step 2: Install the Packages

**TypeScript** (Node.js 20+)
```bash
npm install genkit genkitx-valkey @genkit-ai/googleai
```

**Python** (Python 3.11+)
```bash
pip install genkit genkit-plugin-valkey genkit-plugin-google-genai
```

**Go** (Go 1.22+)
```bash
go get github.com/firebase/genkit/go/plugins/valkey@latest
go get github.com/firebase/genkit/go/plugins/googlegenai@latest
```

## Step 3: Understand the Data Model

All three SDKs store each document as a Valkey HASH with an HNSW vector field:

```
# Key format: {indexName}:{md5_of_document}
# Hash fields:
{
  embedding: <Float32 binary, little-endian>,
  _content:  "The text content of the document",
  _metadata: '{"source":"docs","page":1}',
  _dataType: "text"
}
```

The FT index is created once on startup:

```
FT.CREATE {indexName}_idx ON HASH PREFIX 1 "{indexName}:"
  SCHEMA embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE
         _content TEXT
         _metadata TEXT
```

## Step 4: Initialize the Plugin

**TypeScript**
```typescript
import { genkit } from 'genkit';
import { googleAI } from '@genkit-ai/googleai';
import { valkeyPlugin, valkeyIndexerRef, valkeyRetrieverRef } from 'genkitx-valkey';

const INDEX_NAME = 'my-docs';

const ai = genkit({
  plugins: [
    googleAI(),
    valkeyPlugin([
      {
        indexName: INDEX_NAME,
        embedder: googleAI.embedder('text-embedding-004'),
        dimension: 768,
        clientConfig: {
          addresses: [{ host: 'localhost', port: 6379 }],
        },
      },
    ]),
  ],
});
```

**Python**
```python
from genkit import Genkit
from genkit.plugins.google_genai import GoogleAI
from genkit.plugins.valkey import Valkey, ValkeyConfig

INDEX_NAME = 'my-docs'
DIMENSION = 768  # text-embedding-004

cfg = ValkeyConfig(
    index_name=INDEX_NAME,
    embedder='googleai/text-embedding-004',
    dimension=DIMENSION,
    host='localhost',
    port=6379,
)

ai = Genkit(
    plugins=[
        GoogleAI(),  # reads GOOGLE_GENAI_API_KEY from env
        Valkey(configs=[cfg]),
    ],
)
await ai.registry.initialize_all_plugins()
```

**Go**
```go
import (
    "github.com/firebase/genkit/go/ai"
    "github.com/firebase/genkit/go/genkit"
    "github.com/firebase/genkit/go/plugins/googlegenai"
    valkeyplugin "github.com/firebase/genkit/go/plugins/valkey"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

const indexName = "my-docs"
const dim = 768

g := genkit.Init(ctx, genkit.WithPlugins(
    &googlegenai.GoogleAI{},  // reads GOOGLE_GENAI_API_KEY from env
    &valkeyplugin.Valkey{
        Addresses: []config.NodeAddress{{Host: "localhost", Port: 6379}},
    },
))

embedder, err := googlegenai.GoogleAI{}.DefineEmbedder(g, "text-embedding-004",
    &ai.EmbedderOptions{Dimensions: dim, Label: "text-embedding-004"},
)

ds, retriever, err := valkeyplugin.DefineRetriever(ctx, g, valkeyplugin.Config{
    IndexName: indexName,
    Embedder:  embedder,
    Dimension: dim,
}, nil)
```

## Step 5: Index Documents

**TypeScript**
```typescript
import { Document } from 'genkit';

const indexer = valkeyIndexerRef({ indexName: INDEX_NAME });

await ai.index({
  indexer,
  documents: [
    Document.fromText('Valkey is an open-source, in-memory data store.', { source: 'docs' }),
    Document.fromText('HNSW stands for Hierarchical Navigable Small World.', { source: 'docs' }),
    Document.fromText('Vector search finds semantically similar documents.', { source: 'docs' }),
  ],
});

console.log('✅ Indexed 3 documents');
```

**Python**
```python
from genkit import Document

docs = [
    Document.from_text('Valkey is an open-source, in-memory data store.', metadata={'source': 'docs'}),
    Document.from_text('HNSW stands for Hierarchical Navigable Small World.', metadata={'source': 'docs'}),
    Document.from_text('Vector search finds semantically similar documents.', metadata={'source': 'docs'}),
]
await ai.index(indexer=f'valkey/{INDEX_NAME}', documents=docs)
print('✅ Indexed 3 documents')
```

**Go**
```go
docs := []*ai.Document{
    ai.DocumentFromText("Valkey is an open-source, in-memory data store.", nil),
    ai.DocumentFromText("HNSW stands for Hierarchical Navigable Small World.", nil),
    ai.DocumentFromText("Vector search finds semantically similar documents.", nil),
}
if err := valkeyplugin.Index(ctx, docs, ds); err != nil {
    log.Fatalf("Index: %v", err)
}
fmt.Println("✅ Indexed 3 documents")
```

## Step 6: Retrieve by Meaning

**TypeScript**
```typescript
const retriever = valkeyRetrieverRef({ indexName: INDEX_NAME });

const results = await ai.retrieve({
  retriever,
  query: 'What is Valkey?',
  options: { k: 2 },
});

for (const doc of results) {
  console.log(doc.text);
}

// Output:
// Valkey is an open-source, in-memory data store.
// Vector search finds semantically similar documents.
```

**Python**
```python
response = await ai.retrieve(
    retriever=f'valkey/{INDEX_NAME}',
    query='What is Valkey?',
    options={'k': 2},
)
for doc in response.documents:
    print(doc.text)

# Output:
# Valkey is an open-source, in-memory data store.
# HNSW stands for Hierarchical Navigable Small World.
```

**Go**
```go
query := ai.DocumentFromText("What is Valkey?", nil)

resp, err := genkit.Retrieve(ctx, g,
    ai.WithRetriever(retriever),
    ai.WithDocs(query),
    ai.WithConfig(&valkeyplugin.RetrieverOptions{K: 2}),
)
if err != nil {
    log.Fatalf("Retrieve: %v", err)
}
for _, doc := range resp.Documents {
    fmt.Println(doc.Content[0].Text)
}

// Output:
// Valkey is an open-source, in-memory data store.
// Vector search finds semantically similar documents.
```

## How It Works Under the Hood

| Operation | Valkey Command | Latency |
|-----------|---------------|---------|
| Create index | `FT.CREATE my-docs_idx ON HASH PREFIX 1 "my-docs:" SCHEMA ...` | ~5ms (once) |
| Index document | `HSET my-docs:{md5} embedding <bytes> _content "..." _metadata "{}"` | ~0.3ms |
| Retrieve top-k | `FT.SEARCH my-docs_idx "*=>[KNN 2 @embedding $query_vec]" PARAMS 2 query_vec <bytes>` | ~0.5ms |

**Sources:**
- TypeScript: [`genkitx-valkey`](https://github.com/firebase/genkit/tree/main/js/plugins/valkey)
- Python: [`genkit-plugin-valkey`](https://github.com/firebase/genkit/tree/main/py/plugins/valkey)
- Go: [`go/plugins/valkey`](https://github.com/firebase/genkit/tree/main/go/plugins/valkey)

[Next: 02 Retrieval-Augmented Generation →](02-rag.md)
