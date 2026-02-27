<?php

/**
 * PHP GLIDE Anti-Pattern Demonstrations
 * Based on: https://www.linkedin.com/pulse/5-php-antipatterns-destroy-your-code-how-break-solid-igor-olejar-surse/
 */

echo "PHP GLIDE Anti-Pattern Demonstrations\n";
echo "======================================\n\n";

// ============================================================================
// ANTI-PATTERN 1: God Object (Violates Single Responsibility Principle)
// ============================================================================

echo "=== ANTI-PATTERN: God Object ===\n";

class ValkeyManagerAntiPattern {
    private $client;
    
    public function __construct() {
        $this->client = new ValkeyGlide();
        $this->client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);
    }
    
    // User management
    public function createUser($userId, $data) {
        $this->client->set("user:$userId", json_encode($data));
    }
    
    // Session management
    public function createSession($sessionId, $userId) {
        $this->client->set("session:$sessionId", $userId);
    }
    
    // Cache management
    public function cacheData($key, $value, $ttl) {
        $this->client->setex($key, $ttl, $value);
    }
    
    // Analytics
    public function trackEvent($event) {
        $this->client->incr("analytics:$event");
    }
    
    public function close() {
        $this->client->close();
    }
}

$godManager = new ValkeyManagerAntiPattern();
$godManager->createUser('123', ['name' => 'Alice']);
$godManager->createSession('abc', '123');
$godManager->cacheData('temp', 'data', 60);
$godManager->trackEvent('login');
echo "God object handles everything (VIOLATES SRP)\n";
$godManager->close();

echo "\n=== CORRECT: Separate Responsibilities ===\n";

class ValkeyConnection {
    private $client;
    
    public function __construct() {
        $this->client = new ValkeyGlide();
        $this->client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);
    }
    
    public function getClient() {
        return $this->client;
    }
    
    public function close() {
        $this->client->close();
    }
}

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

$conn = new ValkeyConnection();
$userRepo = new UserRepository($conn->getClient());
$sessionRepo = new SessionRepository($conn->getClient());

$userRepo->createUser('456', ['name' => 'Bob']);
$sessionRepo->createSession('def', '456');
echo "Separate repositories (FOLLOWS SRP)\n";
$conn->close();

// ============================================================================
// ANTI-PATTERN 2: If-Else Chains (Violates Open-Closed Principle)
// ============================================================================

echo "\n=== ANTI-PATTERN: If-Else Chains ===\n";

class CacheStrategyAntiPattern {
    private $client;
    
    public function __construct($client) {
        $this->client = $client;
    }
    
    public function cache($key, $value, $strategy) {
        if ($strategy === 'short') {
            $this->client->setex($key, 60, $value);
        } elseif ($strategy === 'medium') {
            $this->client->setex($key, 3600, $value);
        } elseif ($strategy === 'long') {
            $this->client->setex($key, 86400, $value);
        }
        // Adding new strategy requires modifying this method!
    }
}

$conn = new ValkeyConnection();
$cacheAnti = new CacheStrategyAntiPattern($conn->getClient());
$cacheAnti->cache('test1', 'value', 'short');
echo "If-else chain (must modify for new strategies)\n";
$conn->close();

echo "\n=== CORRECT: Strategy Pattern ===\n";

interface CacheStrategy {
    public function cache($client, $key, $value);
}

class ShortCacheStrategy implements CacheStrategy {
    public function cache($client, $key, $value) {
        $client->setex($key, 60, $value);
    }
}

class MediumCacheStrategy implements CacheStrategy {
    public function cache($client, $key, $value) {
        $client->setex($key, 3600, $value);
    }
}

class CacheManager {
    private $client;
    private $strategy;
    
    public function __construct($client, CacheStrategy $strategy) {
        $this->client = $client;
        $this->strategy = $strategy;
    }
    
    public function cache($key, $value) {
        $this->strategy->cache($this->client, $key, $value);
    }
}

$conn = new ValkeyConnection();
$shortStrategy = new ShortCacheStrategy();
$cacheManager = new CacheManager($conn->getClient(), $shortStrategy);
$cacheManager->cache('test2', 'value');
echo "Strategy pattern (add new strategies without modification)\n";
$conn->close();

// ============================================================================
// ANTI-PATTERN 3: Tight Coupling (Violates Dependency Inversion Principle)
// ============================================================================

echo "\n=== ANTI-PATTERN: Tight Coupling ===\n";

class UserServiceAntiPattern {
    private $client;
    
    public function __construct() {
        // Tightly coupled to ValkeyGlide
        $this->client = new ValkeyGlide();
        $this->client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);
    }
    
    public function getUser($userId) {
        return $this->client->get("user:$userId");
    }
    
    public function close() {
        $this->client->close();
    }
}

$userServiceAnti = new UserServiceAntiPattern();
$userServiceAnti->getUser('123');
echo "Tight coupling (hard to test, hard to swap implementations)\n";
$userServiceAnti->close();

echo "\n=== CORRECT: Dependency Injection ===\n";

interface CacheClient {
    public function get($key);
    public function set($key, $value);
}

class ValkeyGlideAdapter implements CacheClient {
    private $client;
    
    public function __construct() {
        $this->client = new ValkeyGlide();
        $this->client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);
    }
    
    public function get($key) {
        return $this->client->get($key);
    }
    
    public function set($key, $value) {
        return $this->client->set($key, $value);
    }
    
    public function close() {
        $this->client->close();
    }
}

class UserService {
    private $cache;
    
    public function __construct(CacheClient $cache) {
        $this->cache = $cache;
    }
    
    public function getUser($userId) {
        return $this->cache->get("user:$userId");
    }
}

$adapter = new ValkeyGlideAdapter();
$userService = new UserService($adapter);
$userService->getUser('456');
echo "Dependency injection (easy to test, easy to swap)\n";
$adapter->close();

echo "\n=== All demonstrations completed ===\n";
