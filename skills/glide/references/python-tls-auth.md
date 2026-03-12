# Python TLS Authentication

## Password Authentication
```python
from glide import GlideClientConfiguration, NodeAddress, ServerCredentials

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    credentials=ServerCredentials("password"),  # Password only
    # Or with username
    credentials=ServerCredentials("password", "username"),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

## TLS/SSL Configuration

For production with CA-signed certificates:
```python
from glide import AdvancedGlideClientConfiguration
from glide_shared.config import TlsAdvancedConfiguration

# Load CA certificate
with open('ca.crt', 'rb') as f:
    ca_cert = f.read()

tls_config = TlsAdvancedConfiguration(root_pem_cacerts=ca_cert)

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    use_tls=True,
    credentials=ServerCredentials("password"),
    advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

For testing with self-signed certificates (⚠️ not for production):
```python
from glide import AdvancedGlideClientConfiguration
from glide_shared.config import TlsAdvancedConfiguration

# ⚠️ WARNING: Disables certificate verification
tls_config = TlsAdvancedConfiguration(use_insecure_tls=True)

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    use_tls=True,
    credentials=ServerCredentials("password"),
    advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

## AWS ElastiCache IAM Authentication (GLIDE 2.2+)
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
client = await GlideClient.create(config)
```

**Note:** IAM authentication requires GLIDE 2.2 or later. Install with `pip install --upgrade valkey-glide`.

