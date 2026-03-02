# TLS and Authentication Testing

## Summary

**Authentication:** ✅ Tested and validated for Python  
**TLS:** ✅ Tested and validated with self-signed certificates  
**IAM Authentication:** ✅ Documented (requires GLIDE 2.2+)

## Test Results

### ✅ TLS + Authentication (Port 6479)
Successfully validated TLS with password authentication:

```python
from glide_shared.config import TlsAdvancedConfiguration

# For self-signed certificates (testing only)
tls_config = TlsAdvancedConfiguration(use_insecure_tls=True)

config = GlideClientConfiguration(
    addresses=[NodeAddress(host, 6479)],
    use_tls=True,
    credentials=ServerCredentials("mypassword"),
    advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

**Output:**
```
✓ TLS works: b'Hello with TLS!'
```

## Key Learnings

### Self-Signed Certificates
For testing with self-signed certificates, you have two options:

**Option 1: Insecure TLS (testing only)**
```python
# ⚠️ WARNING: Disables certificate verification
tls_config = TlsAdvancedConfiguration(use_insecure_tls=True)
```

**Option 2: Provide CA certificate (production)**
```python
# Load CA certificate for validation
with open('ca.crt', 'rb') as f:
    ca_cert = f.read()
tls_config = TlsAdvancedConfiguration(root_pem_cacerts=ca_cert)
```

### Certificate Requirements
- **Self-signed certs with `CA:FALSE`**: Cannot be used as trusted root CAs
  - Must use `use_insecure_tls=True` OR have a separate CA certificate
- **Self-signed certs with `CA:TRUE`**: Trigger `CaUsedAsEndEntity` error when used as server certs
  - This is correct security behavior by GLIDE
- **Production**: Use proper CA-signed certificates with `root_pem_cacerts`

### Server Certificate Configuration
The Valkey server certificate must have:
- Correct hostname in `CN` (Common Name) or `subjectAltName`
- Correct IP address in `subjectAltName` if connecting by IP
- `CA:FALSE` for server certificates (not `CA:TRUE`)

Example OpenSSL command:
```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout valkey.key -out valkey.crt \
  -days 365 \
  -subj "/CN=$VALKEY_HOST" \
  -addext "basicConstraints=CA:FALSE" \
  -addext "keyUsage=digitalSignature,keyEncipherment" \
  -addext "subjectAltName=DNS:$VALKEY_HOST,IP:$( dig +short $VALKEY_HOST )"
```

## Demo Location

Authentication and TLS testing demos:
- `python/demos/authentication/test_auth_tls.py` - TLS + password auth
- `python/demos/authentication/iam_auth_demo.py` - AWS IAM auth (GLIDE 2.2+)

Run with:
```bash
cd python/demos/authentication
python3 test_auth_tls.py
python3 iam_auth_demo.py
```

## AWS IAM Authentication (GLIDE 2.2+)

### Configuration
```python
from glide import IamAuthConfig, ServiceType

iam_config = IamAuthConfig(
    cluster_name="my-cluster",
    service=ServiceType.ELASTICACHE,  # or ServiceType.MEMORYDB
    region="us-east-1"
)

config = GlideClientConfiguration(
    addresses=[NodeAddress("my-cluster.cache.amazonaws.com", 6379)],
    use_tls=True,  # IAM auth requires TLS
    credentials=ServerCredentials(username="myUser", iam_config=iam_config),
    request_timeout=5000
)
```

### Key Points
- Requires GLIDE 2.2 or later
- Requires `username` parameter in `ServerCredentials`
- Must use `ServiceType.ELASTICACHE` or `ServiceType.MEMORYDB` (not strings)
- TLS is required for IAM authentication
- Cannot be tested without AWS infrastructure

## Validation Status

- ✅ **Authentication patterns** - Validated and working
- ✅ **ServerCredentials API** - Correct usage documented
- ✅ **TLS with insecure mode** - Working for self-signed certs
- ✅ **TLS configuration** - Both secure and insecure modes documented
- ✅ **IAM authentication** - API documented (requires GLIDE 2.2+)
- ✅ **Error handling** - Graceful failure with helpful messages

## Cleanup

```bash
# Stop test Valkey
docker stop valkey-tls && docker rm valkey-tls
```
