# Client Creation Patterns

## Standalone Client
```go
cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithRequestTimeout(10000)

client, err := glide.NewClient(cfg)
if err != nil {
	// Handle error
	return
}
defer client.Close()

ctx := context.Background()
value, err := client.Get(ctx, "key")
```

## Cluster Client
```go
cfg := config.NewClusterClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 7000}).
	WithRequestTimeout(10000)

client, err := glide.NewClusterClient(cfg)
if err != nil {
	// Handle error
	return
}
defer client.Close()
```

**Key Points:**
- Configuration uses builder pattern with `With*()` methods
- Client creation returns `(client, error)` tuple
- Always check `err != nil`
- Use `defer client.Close()` for cleanup
- Context required for all operations

---

## Authentication and TLS

### Password Authentication

```go
import (
	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithCredentials(config.NewServerCredentials("", "mypassword")).
	WithRequestTimeout(5000)

client, err := glide.NewClient(cfg)
if err != nil {
	// Handle error
}
defer client.Close()
```

**With username:**
```go
WithCredentials(config.NewServerCredentials("myuser", "mypassword"))
```

### TLS/SSL Configuration

**For production with CA-signed certificates:**
```go
// Load CA certificate
caCert, err := os.ReadFile("ca.crt")
if err != nil {
	// Handle error
}

tlsConfig := config.NewTlsConfiguration().WithRootCertificates(caCert)
advancedConfig := config.NewAdvancedClientConfiguration().WithTlsConfiguration(tlsConfig)

cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithUseTLS(true).
	WithCredentials(config.NewServerCredentials("", "mypassword")).
	WithRequestTimeout(5000).
	WithAdvancedConfiguration(advancedConfig)

client, err := glide.NewClient(cfg)
```

**For testing with self-signed certificates (⚠️ not for production):**
```go
// ⚠️ WARNING: WithInsecureTLS disables certificate verification
tlsConfig := config.NewTlsConfiguration().WithInsecureTLS(true)
advancedConfig := config.NewAdvancedClientConfiguration().WithTlsConfiguration(tlsConfig)

cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithUseTLS(true).
	WithCredentials(config.NewServerCredentials("", "mypassword")).
	WithRequestTimeout(5000).
	WithAdvancedConfiguration(advancedConfig)

client, err := glide.NewClient(cfg)
```

### AWS ElastiCache IAM Authentication (GLIDE 2.2+)

```go
import "github.com/valkey-io/valkey-glide/go/v2/config"

iamConfig := config.NewIamAuthConfig("my-cluster", config.ElastiCache, "us-east-1")

credentials, err := config.NewServerCredentialsWithIam("myUser", iamConfig)
if err != nil {
	// Handle error
}

cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "my-cluster.cache.amazonaws.com", Port: 6379}).
	WithUseTLS(true).  // IAM auth requires TLS
	WithCredentials(credentials).
	WithRequestTimeout(5000)

client, err := glide.NewClient(cfg)
```

**Key Points:**
- `WithAdvancedConfiguration()` must be called last in the chain
- Use `config.ElastiCache` or `config.MemoryDB` for service type
- IAM requires username in credentials
- Always use `defer client.Close()` for cleanup
