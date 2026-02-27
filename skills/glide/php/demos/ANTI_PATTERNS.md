# PHP GLIDE Anti-Pattern Demonstrations

This demo proves common PHP anti-patterns and their correct alternatives, based on [5 PHP Antipatterns That Will DESTROY Your Code](https://www.linkedin.com/pulse/5-php-antipatterns-destroy-your-code-how-break-solid-igor-olejar-surse/).

## Running the Demo

```bash
cd php
docker build -t php-glide .
docker run --rm -v $(pwd)/demos:/app -e VALKEY_HOST=${VALKEY_HOST} --network host php-glide php /app/anti_patterns.php
```

## Anti-Patterns Demonstrated

### 1. God Object (Violates Single Responsibility Principle)

**Anti-Pattern:**
```php
class ValkeyManagerAntiPattern {
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

**Correct Approach:**
```php
class UserRepository {
    public function createUser($userId, $data) { }
}

class SessionRepository {
    public function createSession($sessionId, $userId) { }
}
```

**Why This Fails:**
- Hard to understand and maintain
- High coupling to many system parts
- Changes ripple through entire class
- Violates separation of concerns

**Demo Output:**
```
=== ANTI-PATTERN: God Object ===
God object handles everything (VIOLATES SRP)

=== CORRECT: Separate Responsibilities ===
Separate repositories (FOLLOWS SRP)
```

---

### 2. If-Else Chains (Violates Open-Closed Principle)

**Anti-Pattern:**
```php
class CacheStrategyAntiPattern {
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
```

**Correct Approach:**
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

**Why This Fails:**
- Must modify class to add new behavior
- Violates Open-Closed Principle
- Difficult to test individual strategies
- Code becomes unmaintainable

**Demo Output:**
```
=== ANTI-PATTERN: If-Else Chains ===
If-else chain (must modify for new strategies)

=== CORRECT: Strategy Pattern ===
Strategy pattern (add new strategies without modification)
```

---

### 3. Tight Coupling (Violates Dependency Inversion Principle)

**Anti-Pattern:**
```php
class UserServiceAntiPattern {
    public function __construct() {
        // Tightly coupled to ValkeyGlide
        $this->client = new ValkeyGlide();
        $this->client->connect(...);
    }
}
```

**Correct Approach:**
```php
interface CacheClient {
    public function get($key);
    public function set($key, $value);
}

class ValkeyGlideAdapter implements CacheClient {
    // Implementation
}

class UserService {
    public function __construct(CacheClient $cache) {
        $this->cache = $cache;
    }
}
```

**Why This Fails:**
- Hard to test (requires real Valkey connection)
- Cannot swap implementations
- Violates Dependency Inversion Principle
- High coupling to concrete class

**Demo Output:**
```
=== ANTI-PATTERN: Tight Coupling ===
Tight coupling (hard to test, hard to swap implementations)

=== CORRECT: Dependency Injection ===
Dependency injection (easy to test, easy to swap)
```

---

## Key Takeaways

1. **Single Responsibility:** One class, one purpose
2. **Open-Closed:** Extend behavior without modifying existing code
3. **Dependency Inversion:** Depend on abstractions, not concrete classes

## SOLID Principles Summary

| Principle | Anti-Pattern | Solution |
|-----------|-------------|----------|
| **S**ingle Responsibility | God Object | Separate classes per responsibility |
| **O**pen-Closed | If-else chains | Strategy pattern with interfaces |
| **L**iskov Substitution | Parent methods that throw in children | Separate interfaces for different capabilities |
| **I**nterface Segregation | Fat interfaces | Split into focused interfaces |
| **D**ependency Inversion | Tight coupling to concrete classes | Inject abstractions (interfaces) |

## Related Resources

- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [PHP Design Patterns](https://refactoring.guru/design-patterns/php)
- [Original Article](https://www.linkedin.com/pulse/5-php-antipatterns-destroy-your-code-how-break-solid-igor-olejar-surse/)
