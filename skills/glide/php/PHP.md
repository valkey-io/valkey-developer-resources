# PHP GLIDE Skill

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

## Summary Checklist

- [ ] Install valkey_glide extension (PECL/pie/source)
- [ ] Enable extension in php.ini: `extension=valkey_glide`
- [ ] Check extension loaded with `extension_loaded('valkey_glide')`
- [ ] Use `ValkeyGlide` for standalone, `ValkeyGlideCluster` for cluster
- [ ] Use `multi()` for atomic transactions
- [ ] Use `pipeline()` for non-atomic pipelines
- [ ] Always call `exec()` to execute queued commands
- [ ] Use hash tags `{tag}` for same-slot keys in cluster
- [ ] Use non-atomic pipeline for multi-slot operations
- [ ] Results are PHP arrays
- [ ] API is synchronous (blocking)
- [ ] PHPRedis compatibility available with `registerPHPRedisAliases()`
- [ ] FT module (vector search) not yet available in v1.0.0
- [ ] **Follow Single Responsibility Principle - one class, one purpose**
- [ ] **Use Strategy Pattern instead of if-else chains**
- [ ] **Inject dependencies via interfaces, not concrete classes**
