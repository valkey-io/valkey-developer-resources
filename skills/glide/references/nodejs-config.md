# Client Creation Patterns

## Standalone Client
```javascript
const { GlideClient } = require("@valkey/valkey-glide");

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  requestTimeout: 10000, // Optional
});
```

## Cluster Client
```javascript
const { GlideClusterClient } = require("@valkey/valkey-glide");

const client = await GlideClusterClient.createClient({
  addresses: [{ host: "localhost", port: 7000 }],
});
```

## Authentication and TLS

### Password Authentication

```javascript
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  credentials: { password: "mypassword" },
  requestTimeout: 5000
});
```

**With username:**
```javascript
credentials: { username: "myuser", password: "mypassword" }
```

### TLS/SSL Configuration

**For production with CA-signed certificates:**
```javascript
const fs = require('fs');

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  useTLS: true,
  credentials: { password: "mypassword" },
  advancedClientConfiguration: {
    tlsAdvancedConfiguration: {
      rootCertificates: fs.readFileSync('ca.crt')
    }
  },
  requestTimeout: 5000
});
```

**For testing with self-signed certificates:**
```javascript
// ⚠️ WARNING: insecure mode may not work in all Node.js GLIDE versions
// If certificate validation is not bypassed, use rootCertificates instead
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  useTLS: true,
  credentials: { password: "mypassword" },
  advancedClientConfiguration: {
    tlsAdvancedConfiguration: {
      insecure: true  // May not bypass validation - see note above
    }
  },
  requestTimeout: 5000
});
```

### AWS ElastiCache IAM Authentication (GLIDE 2.2+)

```javascript
const { GlideClient, ServiceType } = require("@valkey/valkey-glide");

const client = await GlideClient.createClient({
  addresses: [{ host: "my-cluster.cache.amazonaws.com", port: 6379 }],
  useTLS: true,  // IAM auth requires TLS
  credentials: {
    username: "myUser",
    iamConfig: {
      cluster_name: "my-cluster",
      service: ServiceType.Elasticache,  // or ServiceType.MemoryDB
      region: "us-east-1"
    }
  },
  requestTimeout: 5000
});
```

**Key Points:**
- TLS config goes in `advancedClientConfiguration.tlsAdvancedConfiguration`
- Use `ServiceType.Elasticache` or `ServiceType.MemoryDB` (not strings)
- IAM requires username in credentials
- Always call `client.close()` when done

---
