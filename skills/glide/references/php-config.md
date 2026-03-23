# Client Creation Patterns

## Standalone Client
```php
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => 'localhost', 'port' => 6379]]);
```

## Cluster Client
```php
$client = new ValkeyGlideCluster(
    addresses: [
        ['host' => 'localhost', 'port' => 7001],
        ['host' => 'localhost', 'port' => 7002]
    ]
);
```

## PHPRedis Compatibility (PHP 8.3+)
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

