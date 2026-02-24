# Node.js/TypeScript GLIDE Performance Patterns

Language-specific optimization patterns for Node.js and TypeScript implementations using `@valkey/valkey-glide`.

## Quick Wins

### 1. Client Reuse Pattern

**❌ Anti-Pattern: Per-Request Client Creation**
```typescript
// NEVER do this - creates new connection per request
async function handleRequest(req: Request, res: Response) {
    const client = await GlideClient.createClient({
        addresses: [{ host: "localhost", port: 6379 }]
    });
    const data = await client.get("key");
    await client.close();
    res.send(data);
}
```

**✅ Correct: Singleton Client**
```typescript
// Create once at application startup
import { GlideClient, GlideClientConfiguration } from "@valkey/valkey-glide";

const config: GlideClientConfiguration = {
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 500,
    clientName: "my-app-client",
};

const client = await GlideClient.createClient(config);

// Reuse in request handlers
async function handleRequest(req: Request, res: Response) {
    const data = await client.get("key");
    res.send(data);
}

// Graceful shutdown
process.on('SIGTERM', async () => {
    await client.close();
    process.exit(0);
});
```

### 2. Request Timeout Configuration

**Production-Ready Configuration:**

For a complete production-ready configuration example with all recommended settings (timeouts, retry strategies, throughput tuning, AZ affinity), see `assets/config-templates/nodejs-config.ts`.

**✅ Always Configure Timeouts**
```typescript
const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 500, // milliseconds
});
```

**Timeout Guidelines**:
- Real-time apps (sub-10ms): 20-50ms
- Web APIs: 200-500ms
- Background jobs: 1000-5000ms

## Batching Patterns

### Pipeline (Non-Atomic)

**❌ Sequential Operations**
```typescript
// 3 network roundtrips (~15ms)
const user1 = await client.get("user:1");
const user2 = await client.get("user:2");
const user3 = await client.get("user:3");
```

**✅ Pipeline Batch**
```typescript
import { Batch } from "@valkey/valkey-glide";

// 1 network roundtrip (~5ms)
const batch = new Batch(false); // false = pipeline (non-atomic)
batch.get("user:1");
batch.get("user:2");
batch.get("user:3");
const [user1, user2, user3] = await client.exec(batch, true);
```

### Transaction (Atomic)

**✅ Atomic Operations**
```typescript
const transaction = new Batch(true); // true = transaction (atomic)
transaction.set("balance:user:123", "100");
transaction.incr("transaction:count");
transaction.set("last_update", Date.now().toString());

const results = await client.exec(transaction, true);
// All commands succeed or all fail
```

### Batch Size Guidelines

```typescript
// Optimal: 10-100 commands
const batch = new Batch(false);
for (let i = 0; i < 50; i++) {
    batch.get(`key:${i}`);
}
const results = await client.exec(batch, true);

// Avoid: >1000 commands (split into smaller batches)
const keys = Array.from({ length: 5000 }, (_, i) => `key:${i}`);
const batchSize = 100;

for (let i = 0; i < keys.length; i += batchSize) {
    const batch = new Batch(false);
    keys.slice(i, i + batchSize).forEach(key => batch.get(key));
    const results = await client.exec(batch, true);
    // Process results
}
```

## Concurrent Operations

### Promise.all() Pattern

**✅ Concurrent Independent Operations**
```typescript
// Execute concurrently (wall-clock time = max latency)
const [user, posts, comments] = await Promise.all([
    client.get("user:123"),
    client.lrange("posts:123", 0, -1),
    client.lrange("comments:123", 0, -1),
]);
```

**Note**: Batching is usually more efficient than Promise.all() for multiple operations on the same connection.

### Promise.allSettled() for Error Handling

**✅ Handle Partial Failures**
```typescript
const results = await Promise.allSettled([
    client.get("key1"),
    client.get("key2"),
    client.get("key3"),
]);

results.forEach((result, index) => {
    if (result.status === "fulfilled") {
        console.log(`key${index + 1}:`, result.value);
    } else {
        console.error(`key${index + 1} failed:`, result.reason);
    }
});
```

## Cluster Patterns

### Hash Tags for Co-location

**❌ Keys on Different Slots**
```typescript
// Multiple roundtrips to different shards
await client.mget(["user:123:name", "user:123:email", "user:123:age"]);
```

**✅ Hash Tags for Same Slot**
```typescript
// Single roundtrip - all keys on same shard
await client.mget(["{user:123}:name", "{user:123}:email", "{user:123}:age"]);

// Set related data
await client.mset({
    "{user:123}:name": "John",
    "{user:123}:email": "john@example.com",
    "{user:123}:preferences": JSON.stringify({ theme: "dark" }),
});
```

### Cluster Scan

**✅ Iterate All Keys in Cluster**
```typescript
import { ClusterScanCursor } from "@valkey/valkey-glide";

let cursor = new ClusterScanCursor();
const allKeys: string[] = [];

do {
    const [newCursor, keys] = await clusterClient.scan(cursor, {
        match: "user:*",
        count: 100,
    });
    cursor = newCursor;
    allKeys.push(...keys);
} while (!cursor.isFinished());

console.log(`Found ${allKeys.length} keys`);
```

## AZ Affinity Configuration

**✅ Enable for Read-Heavy Workloads**
```typescript
import { GlideClusterClient, GlideClusterClientConfiguration, ReadFrom } from "@valkey/valkey-glide";

const config: GlideClusterClientConfiguration = {
    addresses: [{ host: "cluster.endpoint.cache.amazonaws.com", port: 6379 }],
    readFrom: "AZAffinity" as ReadFrom,
    clientAz: "us-east-1a", // Your application's AZ
    requestTimeout: 500,
};

const client = await GlideClusterClient.createClient(config);
```

**Requirements**:
- Valkey 8.0+ or ElastiCache for Valkey 7.2+
- Cluster mode with replicas
- Read-heavy workload (>80% reads)

## Error Handling

### Typed Error Handling

**✅ Handle Specific Error Types**
```typescript
import { ConnectionError, TimeoutError, RequestError } from "@valkey/valkey-glide";

try {
    const result = await client.get("key");
} catch (error) {
    if (error instanceof TimeoutError) {
        // Retry with exponential backoff
        console.error("Request timed out");
    } else if (error instanceof ConnectionError) {
        // Circuit breaker pattern
        console.error("Connection failed");
    } else if (error instanceof RequestError) {
        // Server error - check command syntax
        console.error("Request error:", error.message);
    } else {
        // Unknown error
        console.error("Unexpected error:", error);
    }
}
```

### Retry Strategy Configuration

**✅ Configure Connection Backoff**
```typescript
const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    connectionBackoff: {
        numberOfRetries: 10,
        factor: 500,        // Base delay in ms
        exponentBase: 2,    // Exponential backoff (500ms, 1s, 2s, 4s, ...)
    },
    requestTimeout: 500,
});
```

## Advanced Patterns

### Serverless/Lambda Optimization

**✅ Lazy Connection**
```typescript
const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    lazyConnect: true, // Don't connect until first command
    requestTimeout: 500,
});

// Connection established on first command
const data = await client.get("key");
```

### Blocking Commands

**✅ Dedicated Client for Blocking Operations**
```typescript
// Separate client for blocking commands
const blockingClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 30000, // 30 seconds
    clientName: "queue-worker",
});

// Use for BLPOP, BRPOP, etc.
const item = await blockingClient.blpop(["queue"], 30);

// Regular client for other operations
const regularClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 500,
    clientName: "app-client",
});
```

### Throughput Tuning

GLIDE uses a single multiplexed connection, not a traditional connection pool. Tune throughput via `inflightRequestsLimit`.

**✅ High-Throughput Configuration**
```typescript
const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    inflightRequestsLimit: 2000, // Default: 1000
    requestTimeout: 500,
});
```

## Data Structures

### Hash vs JSON

**❌ Large JSON Strings**
```typescript
// Inefficient - must fetch/parse entire object
const user = { name: "John", email: "john@example.com", age: 30, ... };
await client.set("user:123", JSON.stringify(user));

const data = await client.get("user:123");
const parsed = JSON.parse(data);
console.log(parsed.name); // Had to fetch everything
```

**✅ Hash Data Structure**
```typescript
// Efficient - fetch only needed fields
await client.hset("user:123", {
    name: "John",
    email: "john@example.com",
    age: "30",
});

// Retrieve single field
const name = await client.hget("user:123", "name");

// Retrieve multiple fields
const [name, email] = await client.hmget("user:123", ["name", "email"]);

// Retrieve all fields
const allFields = await client.hgetall("user:123");
```

## Monitoring

### OpenTelemetry Integration

**✅ Enable Tracing**
```typescript
import { OpenTelemetry } from "@valkey/valkey-glide";

// Initialize once at application startup
OpenTelemetry.init({
    traces: {
        endpoint: "http://localhost:4318/v1/traces",
        samplePercentage: 1, // 1% sampling for production
    },
    metrics: {
        endpoint: "http://localhost:4318/v1/metrics",
    },
});
```

### Logging Configuration

**✅ Production Logging**
```typescript
import { Logger } from "@valkey/valkey-glide";

// Production: minimal logging
Logger.setLoggerConfig("warn", "glide.log");

// Development: verbose logging
Logger.setLoggerConfig("info");

// Maximum performance: errors only
Logger.setLoggerConfig("error");
```

## TypeScript Best Practices

### Type-Safe Configuration

**✅ Use Configuration Interfaces**
```typescript
import { 
    GlideClient, 
    GlideClientConfiguration,
    GlideClusterClient,
    GlideClusterClientConfiguration 
} from "@valkey/valkey-glide";

const config: GlideClientConfiguration = {
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 500,
    clientName: "my-app",
};

const client = await GlideClient.createClient(config);
```

### Type-Safe Command Results

**✅ Type Assertions for Known Data**
```typescript
// Type-safe result handling
const value = await client.get("key");
if (value !== null) {
    const parsed: UserData = JSON.parse(value);
    console.log(parsed.name);
}

// Batch results with proper typing
const batch = new Batch(false);
batch.get("user:1");
batch.get("user:2");
const [user1, user2] = await client.exec(batch, true) as [string | null, string | null];
```

## SCAN vs Valkey-Search

### SCAN for Key Discovery (Scalability Concern)

**❌ SCAN Loop for Pattern-Based Key Lookup**
```typescript
// O(N) full keyspace iteration — degrades as dataset grows
const matched: string[] = [];
let cursor = "0";
do {
    const [newCursor, keys] = await client.scan(cursor, {
        match: pattern,
        count: 100,
    });
    cursor = newCursor;
    matched.push(...keys);
} while (cursor !== "0");

// Then individually fetching each matched key compounds the problem
for (const key of matched) {
    const val = await client.get(key);
    // ...
}
```

**✅ Valkey-Search Index for Efficient Queries**
```typescript
// Create index once at startup
await client.ftCreate("idx:content", {
    prefix: ["content:"],
    schema: [
        { name: "title", type: "TEXT" },
        { name: "tags", type: "TAG" },
    ],
});

// O(K) where K = result count, independent of total keyspace size
const results = await client.ftSearch("idx:content", `@title:${searchTerm}`);
```

**Note**: SCAN is appropriate for one-time migrations or admin tasks. For application-level search or filtering, Valkey-Search (`FT.*`) scales independently of keyspace size.

## Common Pitfalls

### 1. Not Awaiting Client Creation

**❌ Missing await**
```typescript
const client = GlideClient.createClient(config); // Missing await!
await client.get("key"); // Error: client is a Promise
```

**✅ Proper await**
```typescript
const client = await GlideClient.createClient(config);
await client.get("key");
```

### 2. Closing Client Too Early

**❌ Premature close**
```typescript
const client = await GlideClient.createClient(config);
await client.set("key", "value");
await client.close();
await client.get("key"); // Error: client is closed
```

**✅ Keep client alive**
```typescript
const client = await GlideClient.createClient(config);
// Use throughout application lifetime
// Close only on shutdown
```

### 3. Mixing Blocking and Non-Blocking Commands

**❌ Blocking on shared client**
```typescript
const client = await GlideClient.createClient(config);
await client.blpop(["queue"], 30); // Blocks all other operations!
await client.get("key"); // Will timeout
```

**✅ Separate clients**
```typescript
const regularClient = await GlideClient.createClient(config);
const blockingClient = await GlideClient.createClient(config);

await blockingClient.blpop(["queue"], 30);
await regularClient.get("key"); // Works fine
```

## Performance Checklist

- [ ] Client created once at startup, not per request
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching used for bulk operations (10-100 commands)
- [ ] Promise.all() for concurrent independent operations
- [ ] Hash tags for related keys in cluster
- [ ] AZ affinity enabled for read-heavy workloads
- [ ] Error handling with typed exceptions
- [ ] Connection backoff configured
- [ ] Dedicated client for blocking commands
- [ ] Hash data structures for structured data
- [ ] OpenTelemetry enabled for monitoring
- [ ] Logging set to warn/error for production
- [ ] lazyConnect for serverless/Lambda
