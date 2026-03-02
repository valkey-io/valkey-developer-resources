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

## Authentication and TLS

### Password Authentication

```javascript
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  credentials: { password: "mypassword" },
  requestTimeout: 5000
});
```

**With username:**
```javascript
credentials: { username: "myuser", password: "mypassword" }
```

### TLS/SSL Configuration

**For production with CA-signed certificates:**
```javascript
const fs = require('fs');

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  useTLS: true,
  credentials: { password: "mypassword" },
  advancedClientConfiguration: {
    tlsAdvancedConfiguration: {
      rootCertificates: fs.readFileSync('ca.crt')
    }
  },
  requestTimeout: 5000
});
```

**For testing with self-signed certificates:**
```javascript
// ⚠️ WARNING: insecure mode may not work in all Node.js GLIDE versions
// If certificate validation is not bypassed, use rootCertificates instead
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  useTLS: true,
  credentials: { password: "mypassword" },
  advancedClientConfiguration: {
    tlsAdvancedConfiguration: {
      insecure: true  // May not bypass validation - see note above
    }
  },
  requestTimeout: 5000
});
```

### AWS ElastiCache IAM Authentication (GLIDE 2.2+)

```javascript
const { GlideClient, ServiceType } = require("@valkey/valkey-glide");

const client = await GlideClient.createClient({
  addresses: [{ host: "my-cluster.cache.amazonaws.com", port: 6379 }],
  useTLS: true,  // IAM auth requires TLS
  credentials: {
    username: "myUser",
    iamConfig: {
      cluster_name: "my-cluster",
      service: ServiceType.Elasticache,  // or ServiceType.MemoryDB
      region: "us-east-1"
    }
  },
  requestTimeout: 5000
});
```

**Key Points:**
- TLS config goes in `advancedClientConfiguration.tlsAdvancedConfiguration`
- Use `ServiceType.Elasticache` or `ServiceType.MemoryDB` (not strings)
- IAM requires username in credentials
- Always call `client.close()` when done

---

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

## Best Practices

### Async Iteration
When processing multiple keys, avoid `forEach` with async callbacks:

```javascript
// ❌ Wrong - forEach doesn't await (fire-and-forget)
keys.forEach(async (key) => {
  await client.del(key);  // These run immediately, not sequentially
});
console.log("Done!"); // Lies - operations still running

// ✅ Correct - Sequential with for...of
for (const key of keys) {
  await client.del(key);
}
console.log("Actually done");

// ✅ Correct - Parallel with Promise.all
await Promise.all(keys.map(key => client.del(key)));
console.log("All operations complete");

// ✅ Best - Use batch for multiple operations
const batch = new Batch(false);
keys.forEach(key => batch.del([key]));
await client.exec(batch, true);
```

### TypeScript Runtime Validation
If using TypeScript, validate external data at runtime:

```javascript
import { z } from "zod";

// ✅ Validate FT.SEARCH results
const SearchResultSchema = z.tuple([
  z.number(),
  z.array(z.object({
    key: z.instanceof(Buffer),
    value: z.array(z.any())
  }))
]);

const results = SearchResultSchema.parse(
  await GlideFt.search(client, "idx", query, { decoder: Decoder.Bytes })
);

// Now TypeScript knows the exact shape, and runtime validates it
const [count, documents] = results;
```

### Resource Cleanup
Always close clients in finally blocks:

```javascript
const client = await GlideClient.createClient({...});

try {
  await client.set("key", "value");
} finally {
  client.close();  // Ensures cleanup even if error occurs
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

### 5. forEach with Async Callbacks
```javascript
// ❌ Wrong - fire-and-forget (operations not awaited)
keys.forEach(async (key) => {
  await client.del(key);
});

// ✅ Correct - sequential
for (const key of keys) {
  await client.del(key);
}

// ✅ Correct - parallel
await Promise.all(keys.map(key => client.del(key)));
```

### 6. Missing finally Block
```javascript
// ❌ Wrong - client not closed if error occurs
const client = await GlideClient.createClient({...});
await client.set("key", "value");
client.close();

// ✅ Correct - always closes
const client = await GlideClient.createClient({...});
try {
  await client.set("key", "value");
} finally {
  client.close();
}
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
- [ ] Avoid `forEach` with async callbacks - use `for...of` or `Promise.all`
- [ ] Always close client in `finally` block
- [ ] Use batch operations instead of loops for multiple keys
- [ ] Validate external data at runtime (TypeScript with Zod)
