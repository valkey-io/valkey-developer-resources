# GLIDE Configuration Templates

Production-ready configuration templates for Valkey GLIDE clients across all supported languages.

## Available Templates

- `nodejs-config.ts` - Node.js/TypeScript configuration
- `python-config.py` - Python async/sync configuration
- `java-config.java` - Java configuration
- `go-config.go` - Go configuration
- `php-config.php` - PHP configuration

## Configuration Features

All templates include:

- **Request Timeout**: 500ms (recommended for web apps)
- **Connection Retry Strategy**: Exponential backoff (10 retries, 500ms base, 2x multiplier)
- **Client Name**: Descriptive name for debugging
- **Lazy Connect**: Optional for serverless/Lambda deployments
- **High-Throughput**: `inflightRequestsLimit` set to 2000 for high-performance scenarios

Cluster templates additionally include:

- **AZ Affinity**: Cost optimization for read-heavy workloads
- **Read Strategy**: Configured for same-AZ reads

## Usage

### Node.js/TypeScript

```typescript
import { createClients, closeClients } from './config/nodejs-config';

// At application startup
const { standalone, cluster } = await createClients();

// Use clients
const value = await standalone.get('key');

// At shutdown
await closeClients(standalone, cluster);
```

### Python (Async)

```python
from config.python_config import create_async_clients, close_async_clients

# At application startup
standalone, cluster = await create_async_clients()

# Use clients
value = await standalone.get('key')

# At shutdown
await close_async_clients(standalone, cluster)
```

### Python (Sync)

```python
from config.python_config import create_sync_client, close_sync_client

# At application startup
standalone = create_sync_client()

# Use clients
value = standalone.get('key')

# At shutdown
close_sync_client(standalone)
```

### Java

```java
import com.example.GlideConfig;

// At application startup
GlideConfig.Clients clients = new GlideConfig.Clients();

// Use clients
String value = clients.getStandalone().get("key").get();

// At shutdown
clients.close();
```

### Go

```go
import "github.com/example/config"

// At application startup
clients, err := config.CreateClients()
if err != nil {
    log.Fatal(err)
}
defer clients.Close()

// Use clients
value, err := clients.Standalone.Get(ctx, "key")
```

### PHP

```php
require_once 'config/php-config.php';

// Clients are created globally and reused
function handleRequest() {
    global $glide_standalone;
    
    try {
        $value = $glide_standalone->get('key');
        return $value;
    } catch (ValkeyGlideException $e) {
        error_log("Valkey error: " . $e->getMessage());
        throw $e;
    }
}
```

## Customization

### Timeout Values

Adjust `requestTimeout` based on your use case:

- **Real-time apps** (sub-10ms): 20-50ms
- **Web applications**: 200-500ms (default)
- **Batch processing**: 1000-5000ms

### Connection Retry Strategy

Adjust the reconnect/backoff strategy parameters (parameter name varies by language: `connectionBackoff` in Node.js, `reconnect_strategy` in Python/PHP, `reconnectStrategy` in Java, `WithReconnectStrategy` in Go):

- `numberOfRetries`: Number of retry attempts (default: 10)
- `factor`: Base delay in milliseconds (default: 500)
- `exponentBase`: Exponential multiplier (default: 2)

Example backoff sequence: 500ms, 1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s

### High-Throughput Scenarios

For applications requiring >100K ops/sec:

- Increase `inflightRequestsLimit` from 1000
- Reduce `requestTimeout` to 200ms or lower

### AZ Affinity (Cluster Only)

Enable for read-heavy workloads (>80% reads):

- Set the read strategy to AZ Affinity (parameter name and value format vary by language)
- Configure the client AZ to match your application's availability zone
- Requires Valkey 8.0+ or AWS ElastiCache for Valkey 7.2+

### Serverless/Lambda

For serverless deployments:

- Set `lazyConnect` to `true`
- Consider shorter `requestTimeout` (200-300ms)
- Use global variables (Node.js) or static instances (Java) for connection reuse

## Best Practices

1. **Create clients once** at application startup, not per request
2. **Reuse client instances** across all requests
3. **Configure timeouts** appropriate for your use case
4. **Enable retry strategy** for resilience
5. **Use AZ affinity** for read-heavy cluster workloads
6. **Set descriptive client names** for debugging
7. **Implement graceful shutdown** to close connections properly

## Additional Resources

- [GLIDE Wiki - Configuration](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#configuration)
- [GLIDE Wiki - Connection Management](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#connection-management)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
- [Performance Checklist](../performance-checklist.md)
