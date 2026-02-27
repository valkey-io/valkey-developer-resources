# PHP GLIDE Performance Patterns

Language-specific optimization patterns for PHP implementations using `valkey-glide-php` (synchronous client).

## Quick Wins

### 1. Client Reuse Pattern

**❌ Anti-Pattern: Per-Request Client Creation**
```php
// NEVER do this - creates new connection per request
function handleRequest($request) {
    $client = new ValkeyGlide();
    $client->connect(addresses: [['host' => 'localhost', 'port' => 6379]]);
    $data = $client->get('key');
    $client->close();
    return $data;
}
```

**✅ Correct: Singleton Client**
```php
// Create once at application startup
// ValkeyGlide constructor takes no arguments; all config goes in connect()
// connect() also accepts PHPRedis-compatible positional params ($host, $port,
// $timeout, $persistent_id, $retry_interval, $read_timeout) for drop-in
// compatibility, but prefer the GLIDE-style named params shown here.
global $valkeyClient;

if (!isset($valkeyClient)) {
    $valkeyClient = new ValkeyGlide();
    $valkeyClient->connect(
        addresses: [['host' => 'localhost', 'port' => 6379]],
        request_timeout: 500,
        client_name: 'my-app-client'
    );
}

// Reuse in request handlers
function handleRequest($request) {
    global $valkeyClient;
    return $valkeyClient->get('key');
}

// Graceful shutdown
register_shutdown_function(function() {
    global $valkeyClient;
    if (isset($valkeyClient)) {
        $valkeyClient->close();
    }
});
```

### 2. Request Timeout Configuration

**Production-Ready Configuration:**

For a complete production-ready configuration example with all recommended settings (timeouts, retry strategies, throughput tuning, AZ affinity), see `assets/config-templates/php-config.php`.

**✅ Always Configure Timeouts**
```php
// Standalone client with timeout
// ValkeyGlide() takes no constructor args; use connect() for all config
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 500  // milliseconds
);

// Cluster client with timeout (all config in constructor)
// ValkeyGlideCluster constructor also accepts PHPRedis RedisCluster-style
// positional params ($name, $seeds, $timeout, $read_timeout, $persistent,
// $auth, $context) for compatibility. Cannot mix styles.
$cluster = new ValkeyGlideCluster(
    addresses: [
        ['host' => 'node1.cluster.local', 'port' => 6379],
        ['host' => 'node2.cluster.local', 'port' => 6379]
    ],
    use_tls: false,
    request_timeout: 500
);
```

## Batching Patterns

### Transaction (MULTI/EXEC) - Atomic

**❌ Sequential Operations**
```php
// 3 network roundtrips (~15ms)
$user1 = $client->get('user:1');
$user2 = $client->get('user:2');
$user3 = $client->get('user:3');
```

**✅ MULTI/EXEC Transaction**
```php
// 1 network roundtrip (~5ms) - atomic execution
$results = $client->multi()
    ->get('user:1')
    ->get('user:2')
    ->get('user:3')
    ->exec();

// $results = ['value1', 'value2', 'value3']
```

**✅ Atomic Write Operations**
```php
$results = $client->multi()
    ->set('balance:user:123', '100')
    ->incr('transaction:count')
    ->set('last_update', (string)time())
    ->exec();
// All commands succeed or all fail
```

### Pipeline (Non-Atomic)

**✅ Pipeline for Independent Operations**
```php
// 1 network roundtrip (~5ms) - non-atomic
$results = $client->pipeline()
    ->get('user:1')
    ->get('user:2')
    ->get('user:3')
    ->exec();
```

**When to Use**:
- **Pipeline**: Multiple independent read operations, no atomicity required
- **MULTI/EXEC**: Operations that must execute atomically

### Batch Size Guidelines

```php
// Optimal: 10-100 commands per batch
// Avoid: >1000 commands (split into smaller batches)
$keys = range(1, 5000);
$batchSize = 100;

foreach (array_chunk($keys, $batchSize) as $batch) {
    $transaction = $client->multi();
    foreach ($batch as $key) {
        $transaction->get("key:$key");
    }
    $results = $transaction->exec();
}
```

## Cluster Patterns

### Hash Tags for Co-location

**❌ Keys on Different Slots**
```php
// May cause CROSSSLOT error in cluster mode
$cluster->mget(['user:123:name', 'user:123:email', 'user:123:age']);
```

**✅ Hash Tags for Same Slot**
```php
// Single roundtrip - all keys on same shard
$values = $cluster->mget(['{user:123}:name', '{user:123}:email', '{user:123}:age']);

// Atomic operations on same-slot keys
$cluster->multi()
    ->set('{order:456}:status', 'pending')
    ->set('{order:456}:total', '99.99')
    ->lpush('{order:456}:items', 'item1', 'item2')
    ->exec();
```

## AZ Affinity Configuration

### Read Strategy Constants

```php
ValkeyGlide::READ_FROM_PRIMARY                          // Always read from primary
ValkeyGlide::READ_FROM_PREFER_REPLICA                   // Prefer replicas, fallback to primary
ValkeyGlide::READ_FROM_AZ_AFFINITY                      // Same-AZ replicas, fallback
ValkeyGlide::READ_FROM_AZ_AFFINITY_REPLICAS_AND_PRIMARY // Same-AZ replicas, then primary, fallback
```

### Enable for Read-Heavy Workloads

**✅ Configure AZ Affinity**
```php
$cluster = new ValkeyGlideCluster(
    addresses: [
        ['host' => 'cluster.endpoint.cache.amazonaws.com', 'port' => 6379]
    ],
    use_tls: false,
    read_from: ValkeyGlide::READ_FROM_AZ_AFFINITY,
    request_timeout: 500,
    client_az: 'us-east-1a',
    periodic_checks: ValkeyGlideCluster::PERIODIC_CHECK_ENABLED_DEFAULT_CONFIGS
);
```

## Error Handling

### Exception Handling

**✅ Try-Catch with Fallback**
```php
function getUserData($userId) {
    global $valkeyClient;

    try {
        $userData = $valkeyClient->get("user:$userId");

        if ($userData !== null) {
            return $userData;
        }

        // Cache miss - fetch from database
        $userData = fetchFromDatabase($userId);

        try {
            $valkeyClient->setex("user:$userId", 3600, $userData);
        } catch (ValkeyGlideException $e) {
            error_log("Failed to cache: " . $e->getMessage());
        }

        return $userData;

    } catch (ValkeyGlideException $e) {
        error_log("Valkey error: " . $e->getMessage());
        return fetchFromDatabase($userId);
    }
}
```

**Common Error Types**:
- Timeout errors: Request exceeds `request_timeout`
- Connection errors: Cannot reach server
- Request errors: Invalid command or arguments
- Cluster errors: CROSSSLOT (use hash tags)

### Retry Strategy Configuration

**✅ Configure Connection Backoff**
```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 500,
    reconnect_strategy: [
        'num_of_retries' => 10,
        'factor' => 2,           // Delay multiplier
        'exponent_base' => 2,    // Exponential backoff base
        'jitter_percent' => 15   // Random jitter to avoid thundering herd
    ]
);
```

## Advanced Patterns

### Serverless / Lambda Optimization

**✅ Lazy Connection**
```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => getenv('VALKEY_ENDPOINT'), 'port' => 6379]],
    request_timeout: 500,
    lazy_connect: true  // Connection deferred until first command
);
```

**✅ Connection Reuse Across Invocations**
```php
// Global variable persists across warm Lambda invocations
global $valkeyClient;

if (!isset($valkeyClient)) {
    $valkeyClient = new ValkeyGlide();
    $valkeyClient->connect(
        addresses: [['host' => getenv('VALKEY_ENDPOINT'), 'port' => 6379]],
        request_timeout: 500,
        lazy_connect: true,
        reconnect_strategy: [
            'num_of_retries' => 3,
            'factor' => 2,
            'exponent_base' => 2,
            'jitter_percent' => 15
        ]
    );
}
```

### Blocking Commands

**❌ Blocking on Shared Client**
```php
// NEVER - blocks all operations for up to 30 seconds
$item = $valkeyClient->blpop(['queue:tasks'], 30);
$userData = $valkeyClient->get('user:123');  // Blocked!
```

**✅ Dedicated Client for Blocking Operations**
```php
$blockingClient = new ValkeyGlide();
$blockingClient->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 35000,  // Longer timeout for blocking commands
    client_name: 'blocking-worker'
);

// Block on dedicated client
$task = $blockingClient->blpop(['queue:tasks'], 30);

// Shared client remains available
$userData = $valkeyClient->get('user:123');
```

**Blocking commands to isolate**: BLPOP, BRPOP, BRPOPLPUSH, BLMOVE, BZPOPMIN, BZPOPMAX

### Worker Connection Management (PHP-FPM)

```php
// Each PHP-FPM worker maintains its own persistent connection
// Initialize in bootstrap file (loaded once per worker)
global $valkeyClient;

if (!isset($valkeyClient)) {
    $valkeyClient = new ValkeyGlide();
    $valkeyClient->connect(
        addresses: [['host' => 'localhost', 'port' => 6379]],
        request_timeout: 500,
        client_name: 'php-fpm-worker-' . getmypid()
    );
}

// PHP-FPM config controls connection count:
// pm.max_children = 20  →  20 connections to Valkey
```

## Data Structures

### Hash vs JSON

**❌ Large JSON Strings**
```php
// Must fetch/parse entire object for any field
$client->set('user:123', json_encode($userData));
$user = json_decode($client->get('user:123'), true);
$email = $user['email'];  // Fetched everything for one field
```

**✅ Hash Data Structure**
```php
// hSet accepts variadic field-value pairs or an associative array
// Variadic form (primary signature):
$client->hSet('user:123', 'name', 'John', 'email', 'john@example.com', 'age', '30');

// Associative array form (also supported):
$client->hSet('user:123', ['name' => 'John', 'email' => 'john@example.com', 'age' => '30']);

// Fetch only what you need
$email = $client->hGet('user:123', 'email');
$fields = $client->hMget('user:123', ['name', 'email']);
$all = $client->hGetAll('user:123');

// Update single field without read-modify-write
$client->hSet('user:123', 'age', '31');
```

## Monitoring

### OpenTelemetry Integration

**✅ Enable Tracing**
```php
use ValkeyGlide\OpenTelemetry\OpenTelemetryConfig;
use ValkeyGlide\OpenTelemetry\TracesConfig;
use ValkeyGlide\OpenTelemetry\MetricsConfig;

$otelConfig = OpenTelemetryConfig::builder()
    ->traces(
        TracesConfig::builder()
            ->endpoint('http://localhost:4318/v1/traces')
            ->samplePercentage(1)  // 1% sampling in production
            ->build()
    )
    ->metrics(
        MetricsConfig::builder()
            ->endpoint('http://localhost:4318/v1/metrics')
            ->build()
    )
    ->flushIntervalMs(5000)  // Optional, defaults to 5000
    ->build();

$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 500,
    advanced_config: [
        'otel' => $otelConfig
    ]
);

// Adjust sampling at runtime (static method, takes int 0-100)
ValkeyGlide::setOtelSamplePercentage(10);
```

**Recommended Sampling Rates**:
- Production: 1-10%
- Staging: 25-50%
- Development: 100%

### Logging

**✅ Error Logging in Catch Blocks**
```php
try {
    $userData = $valkeyClient->hgetall("user:$userId");
} catch (ValkeyGlideException $e) {
    error_log(sprintf(
        "Valkey error [%s]: %s | User: %s",
        get_class($e),
        $e->getMessage(),
        $userId
    ));
    return null;
}
```

## SCAN vs Valkey-Search

**❌ SCAN Loop for Pattern-Based Key Lookup**
```php
// O(N) full keyspace iteration — degrades as dataset grows
$matched = [];
$iterator = null;
do {
    $keys = $client->scan($iterator, $pattern, 100);
    if ($keys !== false) {
        $matched = array_merge($matched, $keys);
    }
} while ($iterator !== "0");

// Then individually fetching each matched key compounds the problem
foreach ($matched as $key) {
    $val = $client->get($key);
    // ...
}
```

**✅ Valkey-Search Index for Efficient Queries**
```php
// Create index once at startup
$client->ftCreate('idx:content', [
    'PREFIX' => ['content:'],
    'SCHEMA' => [
        ['name' => 'title', 'type' => 'TEXT'],
        ['name' => 'tags', 'type' => 'TAG'],
    ],
]);

// O(K) where K = result count, independent of total keyspace size
$results = $client->ftSearch('idx:content', "@title:{$searchTerm}");
```

## Common Pitfalls

### 1. Creating Client Per Request

```php
// ❌ 5-50ms connection overhead per request
function handleRequest($request) {
    $client = new ValkeyGlide();
    $client->connect(addresses: [['host' => 'localhost', 'port' => 6379]]);
    return $client->get('key');
}

// ✅ Zero overhead after initial setup
global $valkeyClient;
function handleRequest($request) {
    global $valkeyClient;
    return $valkeyClient->get('key');
}
```

### 2. Sequential Commands in Loop

```php
// ❌ N roundtrips
foreach ($userIds as $id) {
    $client->set("user:$id:status", 'active');  // 100 roundtrips!
}

// ✅ 1 roundtrip
$transaction = $client->multi();
foreach ($userIds as $id) {
    $transaction->set("user:$id:status", 'active');
}
$transaction->exec();
```

### 3. No Error Handling

```php
// ❌ Crashes on any Valkey error
$data = $valkeyClient->get("user:$userId");

// ✅ Graceful degradation
try {
    $data = $valkeyClient->get("user:$userId");
} catch (ValkeyGlideException $e) {
    error_log("Valkey error: " . $e->getMessage());
    $data = fetchFromDatabase($userId);
}
```

### 4. Blocking Commands on Shared Client

```php
// ❌ Blocks all operations
$valkeyClient->blpop(['queue'], 30);

// ✅ Use dedicated client or polling with LPOP
$item = $valkeyClient->lpop('queue');
```

## Additional Performance Checklist

See SKILL.md for universal checklist. Language-specific items:

- [ ] Global/static variable for client reuse
- [ ] ValkeyGlideException try-catch around operations
- [ ] PHP-FPM worker connections managed via pm.max_children
