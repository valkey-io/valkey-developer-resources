# Metadata Filtering

**Intermediate** · TypeScript · Python · Go · ~20 min

## Why Metadata Filtering?

KNN vector search finds the most similar documents across your entire index. But when your index has millions of documents from multiple sources, tenants, or time periods, you want to narrow the search space first. Valkey supports two index field types for pre-filtering:

  * **TAG** - exact-match on string labels (`category`, `tenant_id`, `language`)
  * **NUMERIC** - range queries on numbers (`year`, `price`, `score`)

Pre-filters run before KNN, so only matching documents are considered. This is faster than post-filtering and gives more accurate top-k results.

## Step 1: Declare Metadata Fields at Index Creation

Add metadata field declarations to the plugin config. These become real Valkey index schema fields, not just JSON blobs.

**TypeScript**
```typescript
import { genkit } from 'genkit';
import { googleAI } from '@genkit-ai/googleai';
import { valkeyPlugin, valkeyIndexerRef, valkeyRetrieverRef } from 'genkitx-valkey';

const INDEX_NAME = 'product-docs';

const ai = genkit({
  plugins: [
    googleAI(),
    valkeyPlugin([
      {
        indexName: INDEX_NAME,
        embedder: googleAI.embedder('text-embedding-004'),
        dimension: 768,
        clientConfig: { addresses: [{ host: 'localhost', port: 6379 }] },
        metadataFields: [
          { name: 'category', type: 'TAG' },
          { name: 'language', type: 'TAG' },
          { name: 'year', type: 'NUMERIC' },
        ],
      },
    ]),
  ],
});
```

**Python**
```python
from genkit.plugins.google_genai import GoogleAI
from genkit.plugins.valkey import Valkey, ValkeyConfig
from genkit.plugins.valkey.plugin import MetadataField, MetadataFieldType

cfg = ValkeyConfig(
    index_name='product-docs',
    embedder='googleai/text-embedding-004',
    dimension=768,
    metadata_fields=[
        MetadataField(name='category', field_type=MetadataFieldType.TAG),
        MetadataField(name='language', field_type=MetadataFieldType.TAG),
        MetadataField(name='year', field_type=MetadataFieldType.NUMERIC),
    ],
)
```

**Go**
```go
ds, retriever, err := valkeyplugin.DefineRetriever(ctx, g, valkeyplugin.Config{
    IndexName: "product-docs",
    Embedder:  embedder,
    Dimension: 768,
    MetadataFields: []valkeyplugin.MetadataFieldConfig{
        {Name: "category", Type: valkeyplugin.MetadataFieldTypeTag},
        {Name: "language", Type: valkeyplugin.MetadataFieldTypeTag},
        {Name: "year", Type: valkeyplugin.MetadataFieldTypeNumeric},
    },
}, nil)
```

## Step 2: Index Documents with Metadata

Values for declared fields are stored as top-level HASH fields alongside the embedding.

**TypeScript**
```typescript
const indexer = valkeyIndexerRef({ indexName: INDEX_NAME });

await ai.index({
  indexer,
  documents: [
    Document.fromText('Valkey 8.0 introduces new compression options.',
      { category: 'release-notes', language: 'en', year: 2024 }),
    Document.fromText('Valkey 7.2 adds cluster scaling improvements.',
      { category: 'release-notes', language: 'en', year: 2023 }),
    Document.fromText('How to configure TLS for Valkey connections.',
      { category: 'tutorial', language: 'en', year: 2024 }),
    Document.fromText('Cómo configurar TLS en Valkey.',
      { category: 'tutorial', language: 'es', year: 2024 }),
  ],
});
console.log('✅ Indexed 4 documents with metadata');
```

**Python**
```python
from genkit import Document

docs = [
    Document.from_text('Valkey 8.0 introduces new compression options.',
        metadata={'category': 'release-notes', 'language': 'en', 'year': 2024}),
    Document.from_text('Valkey 7.2 adds cluster scaling improvements.',
        metadata={'category': 'release-notes', 'language': 'en', 'year': 2023}),
    Document.from_text('How to configure TLS for Valkey connections.',
        metadata={'category': 'tutorial', 'language': 'en', 'year': 2024}),
    Document.from_text('Cómo configurar TLS en Valkey.',
        metadata={'category': 'tutorial', 'language': 'es', 'year': 2024}),
]
await ai.index(indexer=f'valkey/{INDEX_NAME}', documents=docs)
print('✅ Indexed 4 documents with metadata')
```

**Go**
```go
docs := []*ai.Document{
    ai.DocumentFromText("Valkey 8.0 introduces new compression options.",
        map[string]any{"category": "release-notes", "language": "en", "year": float64(2024)}),
    ai.DocumentFromText("Valkey 7.2 adds cluster scaling improvements.",
        map[string]any{"category": "release-notes", "language": "en", "year": float64(2023)}),
    ai.DocumentFromText("How to configure TLS for Valkey connections.",
        map[string]any{"category": "tutorial", "language": "en", "year": float64(2024)}),
    ai.DocumentFromText("Cómo configurar TLS en Valkey.",
        map[string]any{"category": "tutorial", "language": "es", "year": float64(2024)}),
}
if err := valkeyplugin.Index(ctx, docs, ds); err != nil {
    log.Fatalf("Index: %v", err)
}
fmt.Println("✅ Indexed 4 documents with metadata")
```

## Step 3: Filter by TAG

TAG filters use `{curly braces}` syntax. Space between expressions means AND.

**TypeScript**
```typescript
const retriever = valkeyRetrieverRef({ indexName: INDEX_NAME });

// Only search within English tutorials
const results = await ai.retrieve({
  retriever,
  query: 'TLS configuration',
  options: { k: 5, filter: '@category:{tutorial} @language:{en}' },
});

for (const doc of results) {
  console.log(doc.text);
}
// Output:
// How to configure TLS for Valkey connections.
```

**Python**
```python
response = await ai.retrieve(
    retriever=f'valkey/{INDEX_NAME}',
    query='TLS configuration',
    options={'k': 5, 'filter': '@category:{tutorial} @language:{en}'},
)
for doc in response.documents:
    print(doc.text)
# Output:
# How to configure TLS for Valkey connections.
```

**Go**
```go
resp, err := genkit.Retrieve(ctx, g,
    ai.WithRetriever(retriever),
    ai.WithDocs(queryDoc),
    ai.WithConfig(&valkeyplugin.RetrieverOptions{
        K:      5,
        Filter: "@category:{tutorial} @language:{en}",
    }),
)
// resp.Documents contains only English tutorials
```

## Step 4: Filter by NUMERIC Range

NUMERIC filters use `[min max]` syntax.

**TypeScript**
```typescript
// Only search 2024 release notes
const results = await ai.retrieve({
  retriever,
  query: 'new features',
  options: { k: 5, filter: '@category:{release-notes} @year:[2024 2024]' },
});
// Output:
// Valkey 8.0 introduces new compression options.
```

**Python**
```python
response = await ai.retrieve(
    retriever=f'valkey/{INDEX_NAME}',
    query='new features',
    options={'k': 5, 'filter': '@category:{release-notes} @year:[2024 2024]'},
)
# response.documents contains only 2024 release notes
```

**Go**
```go
resp, err := genkit.Retrieve(ctx, g,
    ai.WithRetriever(retriever),
    ai.WithDocs(queryDoc),
    ai.WithConfig(&valkeyplugin.RetrieverOptions{
        K:      5,
        Filter: "@category:{release-notes} @year:[2024 2024]",
    }),
)
// resp.Documents contains only 2024 release notes
```

## Step 5: Combining Filters

The filter string syntax is identical across all three SDKs — it is passed directly to Valkey's FT.SEARCH pre-filter.

```
# English docs from 2023 onwards
@language:{en} @year:[2023 +inf]

# Multiple TAG values (OR)
@category:{tutorial|release-notes}

# Combined TAG + NUMERIC
@language:{en} @year:[2024 +inf]
```

**Important:** The `filter` value is interpolated directly into the FT.SEARCH query. Do not pass untrusted user input as a filter. Validate and allowlist filter values in your application before use.

## How It Works Under the Hood

| Operation | Valkey Command | Latency |
|-----------|---------------|---------|
| Create index with fields | `FT.CREATE product-docs_idx ON HASH PREFIX 1 "product-docs:" SCHEMA embedding VECTOR HNSW ... category TAG language TAG year NUMERIC` | ~5ms (once) |
| Index with metadata | `HSET product-docs:{id} embedding <bytes> _content "..." category "tutorial" language "en" year "2024"` | ~0.3ms |
| Filtered KNN search | `FT.SEARCH product-docs_idx "(@category:{tutorial} @language:{en})=>[KNN 5 @embedding $query_vec]" PARAMS 2 query_vec <bytes>` | ~0.5ms |

The pre-filter `(@category:{tutorial} @language:{en})` eliminates non-matching documents before the vector comparison runs, so KNN only scores documents that already pass the filter.

Parameter | Notes
---|---
`TAG` filter | Use `{value}` for exact match; `{val1\|val2}` for OR
`NUMERIC` filter | Use `[min max]`; `-inf` and `+inf` for open bounds
Multiple filters | Space-separated means AND; wrap with `(\|)` for OR

[← 02 Retrieval-Augmented Generation](02-rag.md)
