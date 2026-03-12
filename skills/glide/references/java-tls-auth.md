# TLS and Authentication

## Password Authentication

```java
import glide.api.models.configuration.ServerCredentials;

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .credentials(ServerCredentials.builder()
        .password("mypassword")
        .build())
    .requestTimeout(5000)
    .build();

try (GlideClient client = GlideClient.createClient(config).get()) {
    // Operations
}
```

**With username:**
```java
.credentials(ServerCredentials.builder()
    .username("user")
    .password("mypassword")
    .build())
```

## TLS/SSL Configuration

**For production with CA-signed certificates:**
```java
import glide.api.models.configuration.TlsAdvancedConfiguration;
import glide.api.models.configuration.AdvancedGlideClientConfiguration;
import java.nio.file.Files;
import java.nio.file.Paths;

// Load CA certificate
byte[] caCert = Files.readAllBytes(Paths.get("ca.crt"));

TlsAdvancedConfiguration tlsConfig = TlsAdvancedConfiguration.builder()
    .rootCertificates(caCert)
    .build();

AdvancedGlideClientConfiguration advancedConfig = AdvancedGlideClientConfiguration.builder()
    .tlsAdvancedConfiguration(tlsConfig)
    .build();

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .useTLS(true)  // Enable TLS
    .credentials(ServerCredentials.builder()
        .password("mypassword")
        .build())
    .advancedConfiguration(advancedConfig)
    .requestTimeout(5000)
    .build();

try (GlideClient client = GlideClient.createClient(config).get()) {
    // Operations
}
```

**For testing with self-signed certificates (⚠️ not for production):**
```java
// ⚠️ WARNING: useInsecureTLS disables certificate verification
TlsAdvancedConfiguration tlsConfig = TlsAdvancedConfiguration.builder()
    .useInsecureTLS(true)
    .build();

AdvancedGlideClientConfiguration advancedConfig = AdvancedGlideClientConfiguration.builder()
    .tlsAdvancedConfiguration(tlsConfig)
    .build();

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .useTLS(true)
    .credentials(ServerCredentials.builder()
        .password("mypassword")
        .build())
    .advancedConfiguration(advancedConfig)
    .requestTimeout(5000)
    .build();
```

## AWS ElastiCache IAM Authentication

```java
import glide.api.models.configuration.IamAuthConfig;
import glide.api.models.configuration.ServiceType;

IamAuthConfig iamConfig = IamAuthConfig.builder()
    .clusterName("my-cluster")
    .service(ServiceType.ELASTICACHE)  // or ServiceType.MEMORYDB
    .region("us-east-1")
    .build();

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("my-cluster.cache.amazonaws.com")
        .port(6379)
        .build())
    .useTLS(true)  // IAM auth requires TLS
    .credentials(ServerCredentials.builder()
        .username("myUser")  // Required for IAM
        .iamConfig(iamConfig)
        .build())
    .requestTimeout(5000)
    .build();
```

**Key Points:**
- Method is `useTLS(true)` (capital TLS), not `useTls()`
- Method is `.tlsAdvancedConfiguration()`, not `.tlsAdvancedConfig()`
- Method is `.advancedConfiguration()`, not `.advancedConfig()`
- `useInsecureTLS(true)` disables certificate verification (testing only)
- Always use try-with-resources for automatic client cleanup

