# Metadata Filtering with LangChain.js and Valkey

> Filter vector search results by metadata fields — combining semantic similarity with structured constraints for precise, relevant retrieval.

**Intermediate** · TypeScript · ~15 min

**Who is this for:** Developers who have basic vector search working and need to narrow results by category, price range, status, or other structured attributes without post-filtering in application code.

## Prerequisites

- Completed [01-getting-started.md](./01-getting-started.md) (Valkey running, packages installed, basic vector store working)
- Familiarity with ValkeyVectorStore configuration options

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Why Custom Schema?

By default, ValkeyVectorStore serializes all metadata into a single JSON string field.
You can search vectors, but you **cannot** filter by metadata values — Valkey has no way
to index fields inside an opaque JSON blob.

With `customSchema`, you explicitly declare which metadata fields should be indexed as separate hash fields. This enables:

- **Server-side filtering** — Valkey applies the filter during the vector search, not after
- **Reduced network traffic** — only matching documents are returned
- **Better relevance** — KNN search is scoped to the filtered subset, so all K results are relevant

Without custom schema, your only option is to fetch more results than needed and filter client-side — wasteful and imprecise.

## Defining a Custom Schema

The `customSchema` option maps metadata field names to their index type and configuration:

```typescript
import { ValkeyVectorStore, SchemaFieldTypes } from "@langchain/valkey";

const vectorStore = new ValkeyVectorStore(embeddings, {
  client,
  indexName: "products",
  customSchema: {
    category: {
      type: SchemaFieldTypes.TAG,
      separator: "|",
      required: true,
    },
    price: {
      type: SchemaFieldTypes.NUMERIC,
      required: true,
    },
    description: {
      type: SchemaFieldTypes.TEXT,
    },
  },
});
```

### Schema Field Types

| Type | Use case | Filter behavior |
| --- | --- | --- |
| `SchemaFieldTypes.TAG` | Categories, statuses, labels | Exact match on discrete values |
| `SchemaFieldTypes.NUMERIC` | Prices, ratings, timestamps | Exact match or range queries |
| `SchemaFieldTypes.TEXT` | Full-text searchable fields | Full-text matching (not typically used for filtering) |

### Schema Options

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | `SchemaFieldTypes` | — | The index type for this field |
| `required` | `boolean` | `false` | If `true`, documents without this field will be rejected |
| `separator` | `string` | `","` | TAG only — delimiter for multi-value fields |

## Full Example: Product Catalog Vector Store

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { ValkeyVectorStore, SchemaFieldTypes } from "@langchain/valkey";
import { OpenAIEmbeddings } from "@langchain/openai";
import { Document } from "@langchain/core/documents";

// Connect to Valkey
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const embeddings = new OpenAIEmbeddings({
  model: "text-embedding-3-small",
});

// Create vector store with custom schema
const vectorStore = new ValkeyVectorStore(embeddings, {
  client,
  indexName: "product-catalog",
  customSchema: {
    category: {
      type: SchemaFieldTypes.TAG,
      separator: "|",
      required: true,
    },
    brand: {
      type: SchemaFieldTypes.TAG,
      separator: "|",
    },
    price: {
      type: SchemaFieldTypes.NUMERIC,
      required: true,
    },
    rating: {
      type: SchemaFieldTypes.NUMERIC,
    },
  },
});

// Add product documents
await vectorStore.addDocuments([
  new Document({
    pageContent: "Wireless noise-canceling headphones with 30-hour battery life",
    metadata: { category: "electronics", brand: "SoundMax", price: 299, rating: 4.5 },
  }),
  new Document({
    pageContent: "Professional studio monitor headphones for audio mixing",
    metadata: { category: "electronics", brand: "AudioPro", price: 449, rating: 4.8 },
  }),
  new Document({
    pageContent: "Ergonomic mechanical keyboard with hot-swappable switches",
    metadata: { category: "electronics", brand: "KeyCraft", price: 159, rating: 4.3 },
  }),
  new Document({
    pageContent: "Organic cotton running t-shirt, moisture-wicking fabric",
    metadata: { category: "clothing", brand: "EcoRun", price: 45, rating: 4.1 },
  }),
  new Document({
    pageContent: "Waterproof hiking boots with ankle support and vibram sole",
    metadata: { category: "footwear", brand: "TrailBound", price: 189, rating: 4.6 },
  }),
]);
```

## TAG Filtering

TAG filters perform exact-match comparisons on discrete values.

### Single Value

```typescript
// Find electronics similar to "high quality audio"
const results = await vectorStore.similaritySearchWithScore(
  "high quality audio",
  3,
  { category: "electronics" }
);

for (const [doc, score] of results) {
  console.log(`[${score.toFixed(3)}] ${doc.metadata.brand}: ${doc.pageContent}`);
}
```

Output:

```text
[0.234] AudioPro: Professional studio monitor headphones for audio mixing
[0.287] SoundMax: Wireless noise-canceling headphones with 30-hour battery life
[0.512] KeyCraft: Ergonomic mechanical keyboard with hot-swappable switches
```

### Array Values (OR within a field)

When a TAG field contains multiple values separated by the configured `separator`, any matching value satisfies the filter:

```typescript
// Documents can have multiple categories
await vectorStore.addDocuments([
  new Document({
    pageContent: "Smart fitness watch with GPS and heart rate monitor",
    metadata: { category: "electronics|fitness", brand: "FitTech", price: 249, rating: 4.4 },
  }),
]);

// This document matches a filter for either "electronics" OR "fitness"
const fitnessResults = await vectorStore.similaritySearchWithScore(
  "workout tracking",
  3,
  { category: "fitness" }
);
```

## NUMERIC Filtering

NUMERIC filters support exact values and ranges.

### Exact Match

```typescript
// Find products priced exactly at 299
const exactResults = await vectorStore.similaritySearchWithScore(
  "headphones",
  3,
  { price: 299 }
);
```

### Range Query

Use `{ min, max }` to specify bounds (inclusive):

```typescript
// Find electronics between $100 and $300
const rangeResults = await vectorStore.similaritySearchWithScore(
  "headphones",
  3,
  { category: "electronics", price: { min: 100, max: 300 } }
);
```

### Open-Ended Range

Omit `min` or `max` for one-sided ranges:

```typescript
// Find products under $200
const budgetResults = await vectorStore.similaritySearchWithScore(
  "audio equipment",
  5,
  { price: { max: 200 } }
);

// Find premium products ($400+)
const premiumResults = await vectorStore.similaritySearchWithScore(
  "professional audio",
  5,
  { price: { min: 400 } }
);
```

## Combined Filters

Pass multiple fields to apply all constraints simultaneously (AND logic):

```typescript
// Electronics under $300 from SoundMax
const filtered = await vectorStore.similaritySearchWithScore(
  "wireless audio",
  3,
  {
    category: "electronics",
    brand: "SoundMax",
    price: { max: 300 },
  }
);
```

All filter conditions must match — a document is only returned if it satisfies every specified field.

## How Filters Map to Valkey Commands

Understanding the translation helps with debugging and performance tuning.

When you call:

```typescript
await vectorStore.similaritySearchWithScore("wireless audio", 3, {
  category: "electronics",
  price: { min: 100, max: 300 },
});
```

ValkeyVectorStore builds this Valkey Search query:

```text
FT.SEARCH product-catalog
  "(@metadata.category:{electronics} @metadata.price:[100 300])=>[KNN 3 @content_vector $BLOB AS score]"
  PARAMS 2 BLOB <query_vector_bytes>
  SORTBY score
  DIALECT 2
```

### Filter syntax breakdown

| Filter type | LangChain format | Valkey query syntax |
| --- | --- | --- |
| TAG exact | `{ category: "electronics" }` | `@metadata.category:{electronics}` |
| TAG with spaces | `{ category: "home audio" }` | `@metadata.category:{home\\ audio}` |
| NUMERIC exact | `{ price: 299 }` | `@metadata.price:[299 299]` |
| NUMERIC range | `{ price: { min: 100, max: 300 } }` | `@metadata.price:[100 300]` |
| NUMERIC ≥ | `{ price: { min: 100 } }` | `@metadata.price:[100 +inf]` |
| NUMERIC ≤ | `{ price: { max: 300 } }` | `@metadata.price:[-inf 300]` |

The filter is applied **before** the KNN search — Valkey first narrows the candidate set,
then finds the K nearest neighbors within that subset. This is more efficient than fetching
K results and filtering afterward.

## Schema Validation

### Required Fields

When a field is marked `required: true`, adding a document without that field throws an error:

```typescript
// This will throw — missing required "category" and "price" fields
await vectorStore.addDocuments([
  new Document({
    pageContent: "A product without required metadata",
    metadata: { brand: "Unknown" },
  }),
]);
// Error: Missing required metadata field: category
```

### Type Checking

NUMERIC fields must receive number values. TAG fields must receive strings:

```typescript
// This will throw — price must be a number
await vectorStore.addDocuments([
  new Document({
    pageContent: "Bad price type",
    metadata: { category: "electronics", price: "not a number" },
  }),
]);
// Error: Field "price" expects NUMERIC but received string
```

## Troubleshooting

### Filter returns no results but unfiltered search works

- Verify the custom schema is defined — without it, metadata fields aren't indexed
- Check that the field name in the filter matches the schema key exactly (case-sensitive)
- Confirm documents were added *after* the schema was configured —
  documents added before the schema definition won't have indexed fields

### "Unknown index field" error

The filter references a field not in your `customSchema`. Add it to the schema and re-index:

```bash
# Drop and recreate the index
docker exec valkey valkey-cli FT.DROPINDEX product-catalog
```

Then re-add your documents so the new field is indexed.

### TAG filter doesn't match multi-word values

TAG values containing spaces must be escaped in the raw query. ValkeyVectorStore handles
this automatically when you pass the filter object — but if you're debugging raw queries,
remember to escape spaces with `\\`.

### NUMERIC range returns unexpected results

Both `min` and `max` are inclusive. If you need exclusive bounds, adjust by the smallest
meaningful increment (e.g., `{ min: 100.01 }` instead of `> 100`).

### Schema changes don't take effect

Valkey Search indexes are immutable once created. To change the schema:

1. Drop the index: `docker exec valkey valkey-cli FT.DROPINDEX product-catalog`
2. Delete existing documents: `docker exec valkey valkey-cli DEL $(docker exec valkey valkey-cli KEYS "doc:product-catalog:*")`
3. Restart your application to recreate the index with the new schema

---

**← Previous:** [01-getting-started.md](./01-getting-started.md) · **Next →** [03-rag-pipeline.md](./03-rag-pipeline.md)

**Back to** [README](./README.md)
