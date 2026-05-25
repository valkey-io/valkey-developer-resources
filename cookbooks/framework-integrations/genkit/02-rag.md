# Retrieval-Augmented Generation

**Intermediate** · TypeScript · Python · Go · ~20 min

## The Problem

LLMs hallucinate when answering questions about private or recent data they were never trained on. Retrieval-Augmented Generation (RAG) fixes this by fetching relevant documents from Valkey first, then giving them to the model as grounding context.

With Genkit + Valkey:

  * **Grounded answers** - the model only answers from retrieved documents
  * **Updateable knowledge** - add new documents without retraining
  * **Source attribution** - metadata tells you exactly which document was used

## Step 1: Set Up the AI Instance

Follow [Guide 01](01-getting-started.md) to start Valkey and install dependencies.

**TypeScript**
```typescript
import { genkit, z } from 'genkit';
import { googleAI, gemini15Flash } from '@genkit-ai/googleai';
import { valkeyPlugin, valkeyIndexerRef, valkeyRetrieverRef } from 'genkitx-valkey';
import { Document } from 'genkit';

const INDEX_NAME = 'knowledge-base';

const valkey = valkeyPlugin([
  {
    indexName: INDEX_NAME,
    embedder: googleAI.embedder('text-embedding-004'),
    dimension: 768,
    clientConfig: { addresses: [{ host: 'localhost', port: 6379 }] },
  },
]);

const ai = genkit({
  plugins: [googleAI(), valkey.plugin],
});

// Call valkey.close() during shutdown to release client connections.
```

**Python**
```python
from genkit import Genkit
from genkit.plugins.google_genai import GoogleAI
from genkit.plugins.valkey import Valkey, ValkeyConfig

INDEX_NAME = 'knowledge-base'
DIMENSION = 768

ai = Genkit(
    plugins=[
        GoogleAI(),
        Valkey(configs=[ValkeyConfig(
            index_name=INDEX_NAME,
            embedder='googleai/text-embedding-004',
            dimension=DIMENSION,
        )]),
    ],
    model='googleai/gemini-2.0-flash',
)
await ai.registry.initialize_all_plugins()
```

**Go**
```go
g := genkit.Init(ctx, genkit.WithPlugins(
    &googlegenai.GoogleAI{},
    &valkeyplugin.Valkey{
        Addresses: []config.NodeAddress{{Host: "localhost", Port: 6379}},
    },
))

embedder, _ := googlegenai.GoogleAI{}.DefineEmbedder(g, "text-embedding-004",
    &ai.EmbedderOptions{Dimensions: 768, Label: "text-embedding-004"},
)
ds, retriever, _ := valkeyplugin.DefineRetriever(ctx, g, valkeyplugin.Config{
    IndexName: "knowledge-base",
    Embedder:  embedder,
    Dimension: 768,
}, nil)
```

## Step 2: Index Your Knowledge Base

**TypeScript**
```typescript
const indexer = valkeyIndexerRef({ indexName: INDEX_NAME });

await ai.index({
  indexer,
  documents: [
    Document.fromText(
      'Valkey supports strings, hashes, lists, sets, sorted sets, and streams.',
      { source: 'valkey-docs', topic: 'data-types' }
    ),
    Document.fromText(
      'FT.SEARCH performs full-text and vector similarity search on indexed data.',
      { source: 'valkey-docs', topic: 'search' }
    ),
    Document.fromText(
      'HSET stores multiple field-value pairs in a hash at a given key.',
      { source: 'valkey-docs', topic: 'commands' }
    ),
    Document.fromText(
      'Valkey Cluster distributes data across multiple nodes automatically.',
      { source: 'valkey-docs', topic: 'cluster' }
    ),
  ],
});
console.log('✅ Knowledge base indexed');
```

**Python**
```python
from genkit import Document

docs = [
    Document.from_text(
        'Valkey supports strings, hashes, lists, sets, sorted sets, and streams.',
        metadata={'source': 'valkey-docs', 'topic': 'data-types'},
    ),
    Document.from_text(
        'FT.SEARCH performs full-text and vector similarity search on indexed data.',
        metadata={'source': 'valkey-docs', 'topic': 'search'},
    ),
    Document.from_text(
        'HSET stores multiple field-value pairs in a hash at a given key.',
        metadata={'source': 'valkey-docs', 'topic': 'commands'},
    ),
    Document.from_text(
        'Valkey Cluster distributes data across multiple nodes automatically.',
        metadata={'source': 'valkey-docs', 'topic': 'cluster'},
    ),
]
await ai.index(indexer=f'valkey/{INDEX_NAME}', documents=docs)
print('✅ Knowledge base indexed')
```

**Go**
```go
docs := []*ai.Document{
    ai.DocumentFromText("Valkey supports strings, hashes, lists, sets, sorted sets, and streams.", map[string]any{"source": "valkey-docs"}),
    ai.DocumentFromText("FT.SEARCH performs full-text and vector similarity search on indexed data.", map[string]any{"source": "valkey-docs"}),
    ai.DocumentFromText("HSET stores multiple field-value pairs in a hash at a given key.", map[string]any{"source": "valkey-docs"}),
    ai.DocumentFromText("Valkey Cluster distributes data across multiple nodes automatically.", map[string]any{"source": "valkey-docs"}),
}
if err := ds.Index(ctx, docs); err != nil {
    log.Fatalf("Index: %v", err)
}
fmt.Println("✅ Knowledge base indexed")
```

## Step 3: Retrieve + Generate

**TypeScript**
```typescript
const retriever = valkeyRetrieverRef({ indexName: INDEX_NAME });

const ragFlow = ai.defineFlow(
  {
    name: 'answerWithContext',
    inputSchema: z.object({ question: z.string() }),
    outputSchema: z.object({ answer: z.string(), sources: z.array(z.string()) }),
  },
  async ({ question }) => {
    // 1. Retrieve relevant documents from Valkey
    const docs = await ai.retrieve({
      retriever,
      query: question,
      options: { k: 3 },
    });

    // 2. Generate — Genkit auto-injects docs into the prompt via middleware
    const { text } = await ai.generate({
      model: gemini15Flash,
      prompt: question,
      docs,
    });

    const sources = docs.map((doc) => doc.metadata?.source as string).filter(Boolean);
    return { answer: text, sources };
  }
);

const result = await ragFlow({ question: 'What data types does Valkey support?' });
console.log('Answer:', result.answer);
console.log('Sources:', result.sources);

// Output:
// Answer: Valkey supports strings, hashes, lists, sets, sorted sets, and streams.
// Sources: ['valkey-docs', 'valkey-docs', 'valkey-docs']
```

**Python**
```python
question = 'What data types does Valkey support?'

# 1. Retrieve
response = await ai.retrieve(
    retriever=f'valkey/{INDEX_NAME}',
    query=question,
    options={'k': 3},
)

# 2. Generate — Genkit auto-injects docs into the prompt via middleware
answer = await ai.generate(
    prompt=question,
    docs=response.documents,
)
sources = [doc.metadata.get('source') for doc in response.documents if doc.metadata]

print('Answer:', answer.text)
print('Sources:', sources)

# Output:
# Answer: Valkey supports strings, hashes, lists, sets, sorted sets, and streams.
# Sources: ['valkey-docs', 'valkey-docs', 'valkey-docs']
```

**Go**
```go
question := ai.DocumentFromText("What data types does Valkey support?", nil)

// 1. Retrieve
resp, err := genkit.Retrieve(ctx, g,
    ai.WithRetriever(retriever),
    ai.WithDocs(question),
    ai.WithConfig(&valkeyplugin.RetrieverOptions{K: 3}),
)
if err != nil {
    log.Fatalf("Retrieve: %v", err)
}

// 2. Generate — pass docs via WithDocs; Genkit injects them via middleware
answer, err := genkit.GenerateText(ctx, g,
    ai.WithModelName("googleai/gemini-2.0-flash"),
    ai.WithTextPrompt(question.Content[0].Text),
    ai.WithDocs(resp.Documents...),
)
if err != nil {
    log.Fatalf("Generate: %v", err)
}
fmt.Println("Answer:", answer)
```

## Step 4: Inspect Traces in the Developer UI

Start the Genkit developer UI to see every retrieval and generation step:

```bash
# TypeScript
npx genkit start -- npx ts-node your-flow.ts

# Python
genkit start -- python your_flow.py

# Go
genkit start -- go run main.go
```

Open `http://localhost:4000` to inspect the full trace: which documents were retrieved, what prompt was sent, and what the model returned.

## How It Works Under the Hood

| Operation | Valkey Command | Latency |
|-----------|---------------|---------|
| Embed query | *(Google AI text-embedding-004 call)* | ~50ms |
| KNN retrieval | `FT.SEARCH knowledge-base_idx "*=>[KNN 3 @embedding $query_vec]" RETURN 3 _content _metadata _dataType` | ~0.5ms |
| Generate answer | *(Gemini API call with context)* | ~500ms |

The retrieval step is negligible — the latency budget is dominated by the two API calls on either side.

[← 01 Getting Started](01-getting-started.md) | [Next: 03 Metadata Filtering →](03-metadata-filtering.md)
