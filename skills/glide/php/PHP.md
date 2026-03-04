# PHP GLIDE Skill

## Code Snippets
- [php-config.py](snippets/php-config.py) - Optimized templates for production web applications

## Package Selection

```php
// ✅ Correct - PHP Extension
extension=valkey_glide

// Check if loaded
if (!extension_loaded('valkey_glide')) {
    die('valkey_glide extension not loaded');
}

// ❌ Wrong - Don't use PHPRedis directly
// extension=redis
```

**Installation**: PHP GLIDE is a C extension, not a Composer package. Install via PECL, pie, or build from source. See [Packagist](https://packagist.org/packages/valkey-io/valkey-glide-php) for details.

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

### PHPRedis Compatibility (PHP 8.3+)
```php
// Register aliases for easier migration
ValkeyGlide::registerPHPRedisAliases();

// Now use PHPRedis class names
$client = new Redis();
$client->connect(addresses: [['host' => 'localhost', 'port' => 6379]]);

$cluster = new RedisCluster(
    addresses: [['host' => 'localhost', 'port' => 7001]]
);
```

## Authentication and TLS

### Password Authentication

```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    credentials: ['password' => 'mypassword']
);
```

**With username:**
```php
credentials: ['username' => 'myuser', 'password' => 'mypassword']
```

### TLS/SSL Configuration

```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    use_tls: true,
    credentials: ['password' => 'mypassword']
);
```

**Note:** PHP GLIDE v1.0.0 may not support insecure TLS mode for self-signed certificates. Use proper CA-signed certificates in production.

### AWS ElastiCache IAM Authentication (GLIDE 2.2+)

```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'my-cluster.cache.amazonaws.com', 'port' => 6379]],
    use_tls: true,  // REQUIRED for IAM authentication
    credentials: [
        'username' => 'myUser',  // REQUIRED for IAM
        'iamConfig' => [
            ValkeyGlide::IAM_CONFIG_CLUSTER_NAME => 'my-cluster',
            ValkeyGlide::IAM_CONFIG_REGION => 'us-east-1',
            ValkeyGlide::IAM_CONFIG_SERVICE => ValkeyGlide::IAM_SERVICE_ELASTICACHE,
        ]
    ]
);
```

**Key Points:**
- Use `ValkeyGlide::IAM_SERVICE_ELASTICACHE` or `ValkeyGlide::IAM_SERVICE_MEMORYDB`
- IAM requires username in credentials
- Always call `$client->close()` when done

---

## Synchronous API

All operations are synchronous (blocking):

```php
$value = $client->get('key');
$client->set('key', 'value');
$client->del(['key']);
```

## Batch/Pipeline Operations

### Non-Atomic Pipeline
```php
$pipeline = $client->pipeline();
$pipeline->set('key1', 'value1');
$pipeline->set('key2', 'value2');
$pipeline->get('key1');
$pipeline->get('key2');
$results = $client->exec();
// Returns: [true, true, "value1", "value2"]
```

### Atomic Transaction
```php
$client->multi();
$client->set('counter', '0');
$client->incr('counter');
$client->incr('counter');
$client->get('counter');
$results = $client->exec();
// Returns: [true, 1, 2, "2"]
```

### Retry Strategies

**Note:** PHP GLIDE v1.0.0 does not support batch retry strategies (`retryServerError`, `retryConnectionError`). This feature may be added in future versions.

For production resilience, implement retry logic at the application level:

```php
function executeWithRetry($client, callable $operation, int $maxRetries = 3): mixed {
    $attempt = 0;
    while ($attempt < $maxRetries) {
        try {
            return $operation($client);
        } catch (Exception $e) {
            $attempt++;
            if ($attempt >= $maxRetries) {
                throw $e;
            }
            usleep(100000 * $attempt); // Exponential backoff
        }
    }
}

// Usage
$results = executeWithRetry($client, function($c) {
    $c->multi();
    $c->set('key', 'value');
    $c->get('key');
    return $c->exec();
});
```

See SKILL.md for retry strategy decision matrix (applicable when feature becomes available).

## Cluster Operations

### Hash Tags for Slot Control
```php
// Keys with same hash tag go to same slot
$client->set('{user}:1:name', 'Alice');
$client->set('{user}:1:email', 'alice@example.com');

// Atomic transaction works
$client->multi();
$client->get('{user}:1:name');
$client->get('{user}:1:email');
$results = $client->exec();
```

### Multi-Slot Operations
```php
// Non-atomic pipeline for different slots
$pipeline = $client->pipeline();
$pipeline->set('key1', 'value1');
$pipeline->set('key2', 'value2');
$pipeline->get('key1');
$results = $client->exec();
```

## Error Handling

```php
// Some errors are printed to stderr
$client->lpush('string_key', 'value');
// Prints: "Error executing command: WRONGTYPE..."

// Some errors throw exceptions
try {
    $client->multi();
    $client->set('key1', 'value1');  // Different slots
    $client->set('key2', 'value2');
    $client->exec();
} catch (Exception $e) {
    echo "CROSSSLOT error: " . $e->getMessage();
}
```

## Common Pitfalls

### 1. Forgetting exec()
```php
// ❌ Wrong - commands queued but not executed
$client->multi();
$client->set('key', 'value');

// ✅ Correct
$client->multi();
$client->set('key', 'value');
$results = $client->exec();
```

### 2. CROSSSLOT in Transactions
```php
// ❌ Wrong - different slots
$client->multi();
$client->set('key1', 'value1');
$client->set('key2', 'value2');
$client->exec();  // Error

// ✅ Correct - use hash tags
$client->multi();
$client->set('{user}:1', 'value1');
$client->set('{user}:2', 'value2');
$client->exec();
```

### 3. Extension Not Loaded
```php
// ❌ Wrong - assuming extension is loaded
$client = new ValkeyGlide();

// ✅ Correct - check first
if (!extension_loaded('valkey_glide')) {
    die('valkey_glide extension not loaded. Add extension=valkey_glide to php.ini');
}
$client = new ValkeyGlide();
```

### 4. Wrong Client for Cluster
```php
// ❌ Wrong
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => 'localhost', 'port' => 7000]]);

// ✅ Correct
$client = new ValkeyGlideCluster(
    addresses: [['host' => 'localhost', 'port' => 7000]]
);
```

## Best Practices

### ✅ CORRECT: Single Responsibility Principle
```php
class UserRepository {
    private $client;
    
    public function __construct($client) {
        $this->client = $client;
    }
    
    public function createUser($userId, $data) {
        $this->client->set("user:$userId", json_encode($data));
    }
}

class SessionRepository {
    private $client;
    
    public function __construct($client) {
        $this->client = $client;
    }
    
    public function createSession($sessionId, $userId) {
        $this->client->set("session:$sessionId", $userId);
    }
}
```

### ❌ INCORRECT: God Object
```php
class ValkeyManager {
    // User management
    public function createUser($userId, $data) { }
    
    // Session management
    public function createSession($sessionId, $userId) { }
    
    // Cache management
    public function cacheData($key, $value, $ttl) { }
    
    // Analytics
    public function trackEvent($event) { }
}
```

**Why:** God objects violate Single Responsibility Principle, making code hard to maintain and test.

---

### ✅ CORRECT: Strategy Pattern (Open-Closed Principle)
```php
interface CacheStrategy {
    public function cache($client, $key, $value);
}

class ShortCacheStrategy implements CacheStrategy {
    public function cache($client, $key, $value) {
        $client->setex($key, 60, $value);
    }
}

class CacheManager {
    public function __construct($client, CacheStrategy $strategy) {
        $this->strategy = $strategy;
    }
}
```

### ❌ INCORRECT: If-Else Chains
```php
class CacheManager {
    public function cache($key, $value, $strategy) {
        if ($strategy === 'short') {
            $this->client->setex($key, 60, $value);
        } elseif ($strategy === 'medium') {
            $this->client->setex($key, 3600, $value);
        }
        // Must modify this method to add new strategies!
    }
}
```

**Why:** If-else chains violate Open-Closed Principle - must modify code to extend behavior.

---

### ✅ CORRECT: Dependency Injection (Dependency Inversion Principle)
```php
interface CacheClient {
    public function get($key);
    public function set($key, $value);
}

class ValkeyGlideAdapter implements CacheClient {
    private $client;
    
    public function __construct() {
        $this->client = new ValkeyGlide();
        $this->client->connect(...);
    }
    
    public function get($key) {
        return $this->client->get($key);
    }
}

class UserService {
    public function __construct(CacheClient $cache) {
        $this->cache = $cache;
    }
}
```

### ❌ INCORRECT: Tight Coupling
```php
class UserService {
    public function __construct() {
        // Tightly coupled to ValkeyGlide
        $this->client = new ValkeyGlide();
        $this->client->connect(...);
    }
}
```

**Why:** Tight coupling makes testing difficult and prevents swapping implementations.

## Client Lifecycle Management

One client per PHP-FPM worker (not per request). Use a static property or global:

```php
class Cache {
    private static ?ValkeyGlide $client = null;
    public static function client(): ValkeyGlide {
        if (self::$client === null) {
            self::$client = new ValkeyGlide();
            self::$client->connect(addresses: [['host' => 'localhost', 'port' => 6379]], request_timeout: 500);
        }
        return self::$client;
    }
}
```

---

# Performance Optimization

Config templates: [`snippets/php-config.php`](snippets/php-config.php)

## AZ Affinity

```php
$cluster = new ValkeyGlideCluster(
    addresses: [['host' => 'cluster.endpoint.cache.amazonaws.com', 'port' => 6379]],
    use_tls: false,
    read_from: ValkeyGlide::READ_FROM_AZ_AFFINITY,
    client_az: 'us-east-1a',
    request_timeout: 500,
    periodic_checks: ValkeyGlideCluster::PERIODIC_CHECK_ENABLED_DEFAULT_CONFIGS,
);
```

Read strategy constants: `READ_FROM_PRIMARY`, `READ_FROM_PREFER_REPLICA`, `READ_FROM_AZ_AFFINITY`, `READ_FROM_AZ_AFFINITY_REPLICAS_AND_PRIMARY`.

## Serverless / Lambda & PHP-FPM

```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => getenv('VALKEY_ENDPOINT'), 'port' => 6379]],
    request_timeout: 500,
    lazy_connect: true,  // Defer connection until first command
);
```

For PHP-FPM, each worker maintains its own persistent connection. Connection count = `pm.max_children`:

```php
global $valkeyClient;
if (!isset($valkeyClient)) {
    $valkeyClient = new ValkeyGlide();
    $valkeyClient->connect(
        addresses: [['host' => 'localhost', 'port' => 6379]],
        request_timeout: 500,
        client_name: 'php-fpm-worker-' . getmypid(),
    );
}
```

## Retry Strategy

```php
$client = new ValkeyGlide();
$client->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 500,
    reconnect_strategy: [
        'num_of_retries' => 10,
        'factor' => 2,
        'exponent_base' => 2,
        'jitter_percent' => 15,  // Avoid thundering herd
    ],
);
```

## Dedicated Blocking Client

```php
$blockingClient = new ValkeyGlide();
$blockingClient->connect(
    addresses: [['host' => 'localhost', 'port' => 6379]],
    request_timeout: 35000,
    client_name: 'blocking-worker',
);
$task = $blockingClient->blpop(['queue:tasks'], 30);
```

## Hash vs JSON for Structured Data

```php
// ❌ Inefficient — must fetch/parse entire object
$client->set('user:123', json_encode($userData));
$email = json_decode($client->get('user:123'), true)['email'];

// ✅ Efficient — fetch only needed fields
$client->hSet('user:123', 'name', 'John', 'email', 'john@example.com', 'age', '30');
$email = $client->hGet('user:123', 'email');
```

## Monitoring

### OpenTelemetry

```php
use ValkeyGlide\OpenTelemetry\OpenTelemetryConfig;
use ValkeyGlide\OpenTelemetry\TracesConfig;
use ValkeyGlide\OpenTelemetry\MetricsConfig;

$otelConfig = OpenTelemetryConfig::builder()
    ->traces(TracesConfig::builder()
        ->endpoint('http://localhost:4318/v1/traces')
        ->samplePercentage(1)
        ->build())
    ->metrics(MetricsConfig::builder()
        ->endpoint('http://localhost:4318/v1/metrics')
        ->build())
    ->build();

// Adjust sampling at runtime:
ValkeyGlide::setOtelSamplePercentage(10);
```

Recommended sampling: 1-10% production, 25-50% staging, 100% development.

Server-side config: [`performance/server-configuration-guide.md`](../performance/server-configuration-guide.md)
