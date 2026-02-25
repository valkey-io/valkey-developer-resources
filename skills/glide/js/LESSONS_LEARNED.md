# Node.js GLIDE Lessons Learned

## Import Patterns

### Correct Imports
```javascript
const { GlideClient, GlideClusterClient } = require("@valkey/valkey-glide");
const { GlideFt, Decoder } = require("@valkey/valkey-glide");
```

### Module Structure
- Main client classes: `GlideClient` (standalone), `GlideClusterClient` (cluster)
- FT module: `GlideFt` class with static methods
- Utilities: `Decoder` enum for binary data handling

## Client Creation

### Standalone Client
```javascript
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  requestTimeout: 10000,
});
```

### Cluster Client
```javascript
const client = await GlideClusterClient.createClient({
  addresses: [{ host: "localhost", port: 7000 }],
});
```

## Async Patterns

### Promise-Based API
- All operations return Promises
- Use `async/await` for sequential operations
- Native JavaScript async/await - simplest of all three languages

```javascript
const value = await client.get("key");
await client.set("key", "value");
```

### Error Handling
```javascript
try {
  await client.set("key", "value");
} catch (error) {
  console.error("Error:", error.message);
}
```

## Batch/Pipeline Operations

### Standalone Batch
```javascript
const { Batch } = require("@valkey/valkey-glide");

const batch = new Batch(true); // true = atomic
batch.set("key1", "value1");
batch.get("key1");

const results = await client.exec(batch, true);
```

### Cluster Batch
```javascript
const { ClusterBatch } = require("@valkey/valkey-glide");

const batch = new ClusterBatch(false); // false = non-atomic
batch.set("{user}:1", "Alice");
batch.set("{user}:2", "Bob");

const results = await client.exec(batch, true);
```

### Key Differences
- `Batch` for standalone, `ClusterBatch` for cluster
- Constructor takes boolean: `true` = atomic, `false` = non-atomic
- Atomic batches require all keys in same slot (use hash tags)
- Non-atomic batches can span multiple slots

## Vector Search with FT Module

### Static Method Pattern
```javascript
const { GlideFt, Decoder } = require("@valkey/valkey-glide");

// Create index
await GlideFt.create(client, "idx", [
  {
    name: "vector_field",
    alias: "vec",
    type: "VECTOR",
    attributes: {
      algorithm: "HNSW",
      type: "FLOAT32",
      dimensions: 3,
      distanceMetric: "L2",
    },
  },
], { dataType: "HASH", prefixes: ["product:"] });

// Search with binary data
const queryVector = Buffer.from(new Float32Array([1.0, 2.0, 3.0]).buffer);
const results = await GlideFt.search(client, "idx", "*=>[KNN 2 @vec $v]", {
  params: [{ key: "v", value: queryVector }],
  decoder: Decoder.Bytes, // Required for binary data
});
```

### Critical: Decoder.Bytes for Binary Data
- Vector data is binary (Float32Array)
- Must use `decoder: Decoder.Bytes` in search options
- Without it, UTF-8 decoding fails on binary data
- Results come back as Buffers when using Decoder.Bytes

### Method Naming
- `GlideFt.create()` - create index
- `GlideFt.dropindex()` - drop index (lowercase 'index')
- `GlideFt.search()` - search index

## Cluster Operations

### Hash Tags for Slot Control
```javascript
// Same slot
await client.set("{user}:1:name", "Alice");
await client.set("{user}:1:email", "alice@example.com");

// Atomic batch works
const batch = new ClusterBatch(true);
batch.get("{user}:1:name");
batch.get("{user}:1:email");
```

### CROSSSLOT Errors
- Atomic batches fail if keys are in different slots
- Error: "CROSSSLOT Keys in request don't hash to the same slot"
- Solution: Use hash tags or non-atomic batch

### Multi-Slot Operations
```javascript
// Non-atomic batch for different slots
const batch = new ClusterBatch(false);
batch.del(["key1", "key2", "key3"]); // Can span slots
```

## Type System

### Buffer for Binary Data
```javascript
// Create binary vector
const vector = Buffer.from(new Float32Array([1.0, 2.0, 3.0]).buffer);

// Store in hash
await client.hset("product:1", { vector_field: vector });
```

### Results Handling
```javascript
// FT.SEARCH returns [count, documents]
const [count, docs] = await GlideFt.search(client, "idx", "*");

// Documents are array of {key, value} objects
docs.forEach(doc => {
  console.log(doc.key); // Buffer when using Decoder.Bytes
  console.log(doc.value); // Array of field-value pairs
});
```

## Common Pitfalls

### 1. Wrong Batch Class
```javascript
// ❌ Wrong: Using Batch with cluster client
const batch = new Batch(true);
await clusterClient.exec(batch, true); // Error

// ✅ Correct: Use ClusterBatch
const batch = new ClusterBatch(true);
await clusterClient.exec(batch, true);
```

### 2. Missing Decoder for Binary Data
```javascript
// ❌ Wrong: No decoder for binary vector data
const results = await GlideFt.search(client, "idx", query);
// Error: invalid utf-8 sequence

// ✅ Correct: Use Decoder.Bytes
const results = await GlideFt.search(client, "idx", query, {
  decoder: Decoder.Bytes,
});
```

### 3. Wrong Method Name
```javascript
// ❌ Wrong: dropIndex (camelCase)
await GlideFt.dropIndex(client, "idx"); // Not a function

// ✅ Correct: dropindex (lowercase)
await GlideFt.dropindex(client, "idx");
```

### 4. CROSSSLOT in Atomic Batch
```javascript
// ❌ Wrong: Different slots in atomic batch
const batch = new ClusterBatch(true);
batch.get("key1");
batch.get("key2"); // CROSSSLOT error

// ✅ Correct: Use hash tags or non-atomic
const batch = new ClusterBatch(true);
batch.get("{user}:1");
batch.get("{user}:2"); // Same slot
```

## Comparison with Python and Java

### Python vs Node.js
| Aspect | Python | Node.js |
|--------|--------|---------|
| Async | `await` with asyncio | `await` with Promises |
| Batch | `batch = client.batch(atomic=True)` | `batch = new Batch(true)` |
| FT Module | `await client.ft_create()` | `await GlideFt.create(client)` |
| Binary Data | `bytes()` | `Buffer.from()` |
| Error Handling | `except Exception` | `catch (error)` |

### Java vs Node.js
| Aspect | Java | Node.js |
|--------|------|---------|
| Async | `CompletableFuture<T>` | `Promise<T>` |
| Batch | `new Batch()` | `new Batch(bool)` |
| FT Module | `GlideFt.create(client)` | `GlideFt.create(client)` |
| Binary Data | `GlideString.of(bytes)` | `Buffer.from()` |
| Error Handling | `catch (ExecutionException)` | `catch (error)` |

### Key Insight
Node.js GLIDE has the simplest API:
- Native Promises (no CompletableFuture complexity)
- Standard async/await (no special asyncio setup)
- Buffer is built-in (no GlideString wrapper needed)
- Static methods for FT module (consistent with Java)
