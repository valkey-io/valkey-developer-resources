# Node.js GLIDE Skill

## Package Selection

```javascript
// ✅ Correct
const { GlideClient, GlideClusterClient } = require("@valkey/valkey-glide");

// ❌ Wrong
const valkey = require("valkey"); // Different library
```

## Client Creation

### Standalone Client
```javascript
const { GlideClient } = require("@valkey/valkey-glide");

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  requestTimeout: 10000, // Optional
});
```

### Cluster Client
```javascript
const { GlideClusterClient } = require("@valkey/valkey-glide");

const client = await GlideClusterClient.createClient({
  addresses: [{ host: "localhost", port: 7000 }],
});
```

## Async Patterns

All operations return Promises. Use async/await:

```javascript
async function example() {
  const value = await client.get("key");
  await client.set("key", "value");
}
```

## Batch/Pipeline Operations

### Standalone Batch
```javascript
const { Batch } = require("@valkey/valkey-glide");

// Atomic batch
const batch = new Batch(true);
batch.set("key1", "value1");
batch.get("key1");
const results = await client.exec(batch, true);

// Non-atomic pipeline
const pipeline = new Batch(false);
pipeline.set("key1", "value1");
pipeline.set("key2", "value2");
const results = await client.exec(pipeline, true);
```

### Cluster Batch
```javascript
const { ClusterBatch } = require("@valkey/valkey-glide");

// Atomic batch (requires same slot)
const batch = new ClusterBatch(true);
batch.set("{user}:1", "Alice");
batch.get("{user}:1");
const results = await client.exec(batch, true);

// Non-atomic pipeline (can span slots)
const pipeline = new ClusterBatch(false);
pipeline.set("key1", "value1");
pipeline.set("key2", "value2");
const results = await client.exec(pipeline, true);
```

## Vector Search (FT Module)

### Import
```javascript
const { GlideFt, Decoder } = require("@valkey/valkey-glide");
```

### Create Index
```javascript
await GlideFt.create(
  client,
  "products_idx",
  [
    {
      name: "description_vector",
      alias: "vector",
      type: "VECTOR",
      attributes: {
        algorithm: "HNSW",
        type: "FLOAT32",
        dimensions: 768,
        distanceMetric: "L2",
      },
    },
  ],
  { dataType: "HASH", prefixes: ["product:"] }
);
```

### Store Vectors
```javascript
// Create binary vector from Float32Array
const vector = Buffer.from(new Float32Array([1.0, 2.0, 3.0]).buffer);

await client.hset("product:1", {
  name: "Product A",
  description_vector: vector,
});
```

### Search
```javascript
const queryVector = Buffer.from(new Float32Array([1.5, 2.5, 3.5]).buffer);

const [count, documents] = await GlideFt.search(
  client,
  "products_idx",
  "*=>[KNN 10 @vector $vec]",
  {
    params: [{ key: "vec", value: queryVector }],
    returnAttributes: ["name"],
    decoder: Decoder.Bytes, // Required for binary data
  }
);

console.log(`Found ${count} results`);
documents.forEach(doc => {
  console.log(doc.key); // Buffer
  console.log(doc.value); // Array of field-value pairs
});
```

### Drop Index
```javascript
await GlideFt.dropindex(client, "products_idx"); // Note: lowercase 'index'
```

## Cluster Operations

### Hash Tags for Slot Control
```javascript
// Keys with same hash tag go to same slot
await client.set("{user}:1:name", "Alice");
await client.set("{user}:1:email", "alice@example.com");

// Atomic batch works
const batch = new ClusterBatch(true);
batch.get("{user}:1:name");
batch.get("{user}:1:email");
const results = await client.exec(batch, true);
```

### Multi-Slot Operations
```javascript
// Non-atomic batch for different slots
const batch = new ClusterBatch(false);
batch.del(["key1", "key2", "key3"]);
const results = await client.exec(batch, true);
```

## Error Handling

```javascript
try {
  await client.set("key", "value");
} catch (error) {
  console.error("Error:", error.message);
}
```

## Common Pitfalls

### 1. Wrong Batch Class for Client Type
```javascript
// ❌ Wrong
const batch = new Batch(true);
await clusterClient.exec(batch, true);

// ✅ Correct
const batch = new ClusterBatch(true);
await clusterClient.exec(batch, true);
```

### 2. Missing Decoder.Bytes for Binary Data
```javascript
// ❌ Wrong - UTF-8 decoding fails on binary vectors
const results = await GlideFt.search(client, "idx", query);

// ✅ Correct
const results = await GlideFt.search(client, "idx", query, {
  decoder: Decoder.Bytes,
});
```

### 3. CROSSSLOT Errors in Atomic Batches
```javascript
// ❌ Wrong - different slots
const batch = new ClusterBatch(true);
batch.get("key1");
batch.get("key2"); // CROSSSLOT error

// ✅ Correct - use hash tags
const batch = new ClusterBatch(true);
batch.get("{user}:1");
batch.get("{user}:2");
```

### 4. Wrong Method Name
```javascript
// ❌ Wrong
await GlideFt.dropIndex(client, "idx"); // Not a function

// ✅ Correct
await GlideFt.dropindex(client, "idx"); // lowercase 'index'
```

## Summary Checklist

- [ ] Use `@valkey/valkey-glide` package
- [ ] Choose `GlideClient` (standalone) or `GlideClusterClient` (cluster)
- [ ] Use `async/await` for all operations
- [ ] Use `Batch` for standalone, `ClusterBatch` for cluster
- [ ] Constructor boolean: `true` = atomic, `false` = non-atomic
- [ ] Import `GlideFt` for vector search operations
- [ ] Use `Decoder.Bytes` for binary vector data
- [ ] Use `Buffer.from(new Float32Array(...).buffer)` for vectors
- [ ] Use hash tags `{tag}` for same-slot keys in cluster
- [ ] Use non-atomic batches for multi-slot operations
- [ ] Remember `GlideFt.dropindex()` is lowercase
- [ ] FT.SEARCH returns `[count, documents]` tuple
