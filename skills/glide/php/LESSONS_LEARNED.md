# PHP GLIDE Lessons Learned

## Package Structure

### PHP Extension (Not Composer Package)
- PHP GLIDE is a **C extension**, not a pure PHP library
- Requires compilation with Rust toolchain
- Installed via PECL, pie, or from source
- Must be enabled in php.ini: `extension=valkey_glide`

### Class Names
```php
// Main classes
$client = new ValkeyGlide();           // Standalone
$cluster = new ValkeyGlideCluster();   // Cluster

// PHPRedis compatibility (PHP 8.3+)
ValkeyGlide::registerPHPRedisAliases();
$client = new Redis();                 // Alias for ValkeyGlide
$cluster = new RedisCluster();         // Alias for ValkeyGlideCluster
```

## Client Creation

### Standalone Client
```php
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => 'localhost', 'port' => 6379]]);
```

### Cluster Client
```php
$client = new ValkeyGlideCluster(
    addresses: [
        ['host' => 'localhost', 'port' => 7001],
        ['host' => 'localhost', 'port' => 7002]
    ]
);
```

### Named Parameters
PHP 8.0+ named parameters make configuration clear:
```php
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    use_tls: true,
    credentials: ['username' => 'user', 'password' => 'pass']
);
```

## Authentication and TLS

### Password Authentication
```php
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    credentials: ['password' => 'mypassword']
);

// With username
credentials: ['username' => 'myuser', 'password' => 'mypassword']
```

### TLS Configuration
```php
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    use_tls: true,
    credentials: ['password' => 'mypassword']
);
```

**Note:** PHP GLIDE v1.0.0 may not support insecure TLS mode for self-signed certificates.

### IAM Authentication (GLIDE 2.2+)
```php
$client->connect(
    addresses: [['host' => 'my-cluster.cache.amazonaws.com', 'port' => 6379]],
    use_tls: true,  // Required for IAM
    credentials: [
        'username' => 'myUser',
        'iamConfig' => [
            ValkeyGlide::IAM_CONFIG_CLUSTER_NAME => 'my-cluster',
            ValkeyGlide::IAM_CONFIG_REGION => 'us-east-1',
            ValkeyGlide::IAM_CONFIG_SERVICE => ValkeyGlide::IAM_SERVICE_ELASTICACHE,
        ]
    ]
);
```

## Synchronous API

PHP GLIDE is **synchronous only** - no async/await:
```php
$value = $client->get('key');  // Blocks until complete
$client->set('key', 'value');  // Blocks until complete
```

This is simpler than Node.js (Promises) or Java (CompletableFuture).

## Batch/Pipeline Operations

### Non-Atomic Pipeline
```php
$pipeline = $client->pipeline();
$pipeline->set('key1', 'value1');
$pipeline->set('key2', 'value2');
$pipeline->get('key1');
$results = $client->exec();  // Returns array of results
```

### Atomic Transaction
```php
$client->multi();
$client->set('counter', '0');
$client->incr('counter');
$client->get('counter');
$results = $client->exec();  // Returns array of results
```

### Key Differences from Other Languages
- Uses `multi()` and `pipeline()` methods (PHPRedis-compatible)
- No separate Batch/ClusterBatch classes
- `exec()` executes and returns results
- Results are PHP arrays, not objects

### Retry Strategies
**Note:** PHP GLIDE v1.0.0 does not support batch retry strategies (`retryServerError`, `retryConnectionError`). This feature may be added in future versions. For now, implement retry logic at the application level if needed.

See SKILL.md for retry strategy decision matrix (applicable when feature becomes available).

## Error Handling

### Errors Printed, Not Always Thrown
```php
// Error is printed to stderr but doesn't throw exception
$client->lpush('string_key', 'value');  // Prints: "Error executing command: WRONGTYPE..."

// Some errors may throw exceptions
try {
    $client->multi();
    $client->set('key1', 'value1');  // Different slots
    $client->set('key2', 'value2');
    $client->exec();
} catch (Exception $e) {
    echo "CROSSSLOT error: " . $e->getMessage();
}
```

### Exception Types
- Base: `Exception` (generic PHP exception)
- May have `ValkeyGlideException` (not confirmed in testing)
- PHPRedis compatibility: `RedisException` when using aliases

## Cluster Operations

### Hash Tags for Slot Control
```php
// Same slot
$client->set('{user}:1:name', 'Alice');
$client->set('{user}:1:email', 'alice@example.com');

// Atomic transaction works
$client->multi();
$client->get('{user}:1:name');
$client->get('{user}:1:email');
$results = $client->exec();
```

### CROSSSLOT Errors
```php
// Atomic transaction fails with different slots
$client->multi();
$client->set('key1', 'value1');  // Slot A
$client->set('key2', 'value2');  // Slot B
$client->exec();  // Error: "Received crossed slots in pipeline- CrossSlot"
```

### Multi-Slot Pipeline
```php
// Non-atomic pipeline can span slots
$pipeline = $client->pipeline();
$pipeline->set('key1', 'value1');
$pipeline->set('key2', 'value2');
$results = $client->exec();  // Works!
```

## Type System

### PHP Arrays for Everything
```php
// Addresses
$addresses = [['host' => 'localhost', 'port' => 6379]];

// Results
$results = $client->exec();  // Array: [true, true, "value"]

// Multi-key operations
$client->del(['key1', 'key2', 'key3']);
```

### Type Juggling
```php
$client->set('counter', '0');   // String
$client->incr('counter');       // Returns int 1
$client->get('counter');        // Returns string "1"
```

## Common Pitfalls

### 1. Forgetting to Call exec()
```php
// ❌ Wrong: Commands queued but not executed
$client->multi();
$client->set('key', 'value');
// Missing exec()!

// ✅ Correct
$client->multi();
$client->set('key', 'value');
$results = $client->exec();
```

### 2. CROSSSLOT in Transactions
```php
// ❌ Wrong: Different slots in transaction
$client->multi();
$client->set('key1', 'value1');
$client->set('key2', 'value2');
$client->exec();  // Error

// ✅ Correct: Use hash tags
$client->multi();
$client->set('{user}:1', 'value1');
$client->set('{user}:2', 'value2');
$client->exec();
```

### 3. Extension Not Loaded
```php
// Check if extension is loaded
if (!extension_loaded('valkey_glide')) {
    die('valkey_glide extension not loaded');
}
```

### 4. Wrong Client for Cluster
```php
// ❌ Wrong: ValkeyGlide for cluster
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => 'localhost', 'port' => 7000]]);

// ✅ Correct: ValkeyGlideCluster for cluster
$client = new ValkeyGlideCluster(
    addresses: [['host' => 'localhost', 'port' => 7000]]
);
```

## Comparison with Other Languages

### PHP vs Node.js
| Aspect | PHP | Node.js |
|--------|-----|---------|
| Type | C Extension | Native Module |
| Async | Synchronous only | Promises/async-await |
| Batch | `multi()` / `pipeline()` | `new Batch(bool)` |
| Results | PHP arrays | JavaScript arrays |
| Error Handling | Printed + exceptions | try-catch |

### PHP vs Java
| Aspect | PHP | Java |
|--------|-----|-----|
| Type | C Extension | JAR Library |
| Async | Synchronous | CompletableFuture |
| Batch | `multi()` / `pipeline()` | `new Batch()` |
| Results | PHP arrays | Generic types |
| Error Handling | Exceptions | ExecutionException |

### PHP vs Go
| Aspect | PHP | Go |
|--------|-----|-----|
| Type | C Extension | Go Module |
| Async | Synchronous | Synchronous + Context |
| Batch | `multi()` / `pipeline()` | `NewStandaloneBatch()` |
| Results | PHP arrays | `[]any` |
| Error Handling | Exceptions | `if err != nil` |

## Key Insights

1. **PHPRedis-Compatible API**: Designed as drop-in replacement for PHPRedis
2. **Synchronous Only**: Simplest API - no async complexity
3. **C Extension**: Requires compilation, not a pure PHP package
4. **No FT Module Yet**: Vector search not available in PHP GLIDE v1.0.0
5. **Array-Based**: Everything uses PHP arrays (addresses, results, keys)
6. **Error Handling Mixed**: Some errors print, some throw exceptions
7. **Docker Recommended**: Complex build dependencies make Docker ideal for development

## Anti-Patterns and Best Practices

See [ANTI_PATTERNS.md](demos/ANTI_PATTERNS.md) for working demonstrations of:

1. **God Object:** Violates Single Responsibility Principle
2. **If-Else Chains:** Violates Open-Closed Principle
3. **Tight Coupling:** Violates Dependency Inversion Principle

**Key Findings from Anti-Pattern Analysis:**

- **Single Responsibility:** Separate classes for separate concerns (UserRepository, SessionRepository)
- **Open-Closed:** Use Strategy Pattern instead of if-else chains for extensibility
- **Dependency Inversion:** Inject interfaces, not concrete classes, for testability and flexibility

**SOLID Principles Applied to PHP GLIDE:**
- Create focused repository classes (one per domain entity)
- Use interfaces for cache strategies (short, medium, long TTL)
- Inject `CacheClient` interface instead of concrete `ValkeyGlide` class
- Makes code testable, maintainable, and extensible
