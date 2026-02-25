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
- **High-Throughput**: `inflightRequestsLimit` set to 2000 for high-performance scenarios (Node.js, Python, Java; not available in Go)

Cluster templates additionally include:

- **AZ Affinity**: Cost optimization for read-heavy workloads
- **Read Strategy**: Configured for same-AZ reads

## Usage

### Node.js/TypeScript

```typescript
import { GlideClient, GlideClusterClient } from '@valkey/valkey-glide';

const standalone = await GlideClient.createClient(standaloneConfig);
const value = await standalone.get('key');
standalone.close();
```

### Python (Async)

```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

standalone = await GlideClient.create(async_standalone_config)
value = await standalone.get('key')
await standalone.close()
```

### Python (Sync)

```python
from glide_sync import GlideClient as GlideClientSync

standalone = GlideClientSync.create(sync_standalone_config)
value = standalone.get('key')
standalone.close()
```

### Java

```java
import glide.api.GlideClient;

GlideConfig.Clients clients = new GlideConfig.Clients();
String value = clients.getStandalone().get("key").get();
clients.close();
```

### Go

```go
clients, err := config.CreateClients()
if err != nil {
    log.Fatal(err)
}
defer clients.Close()
value, err := clients.Standalone.Get(ctx, "key")
```

### PHP

```php
$client = new ValkeyGlide();
$client->connect(/* see php-config.php for full config */);
$value = $client->get('key');
```

## Customization

See `SKILL.md` for full details on timeout values, retry strategies, throughput tuning, AZ affinity, and serverless configuration.

Key parameter name differences across languages:

| Setting | Node.js | Python | Java | Go | PHP |
|---------|---------|--------|------|----|-----|
| Retry strategy | `connectionBackoff` | `reconnect_strategy` | `reconnectStrategy` | `WithReconnectStrategy` | `reconnect_strategy` |
| Inflight limit | `inflightRequestsLimit` | `inflight_requests_limit` | `inflightRequestsLimit` | N/A | N/A |
| Lazy connect | `lazyConnect` | `lazy_connect` | `lazyConnect` | `WithLazyConnect` | `lazy_connect` |

## Additional Resources

- [GLIDE Wiki](https://glide.valkey.io/)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
