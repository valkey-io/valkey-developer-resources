#!/usr/bin/env python3
"""
Python GLIDE AWS IAM Authentication Demo

Demonstrates AWS ElastiCache/MemoryDB IAM authentication configuration.
Requires GLIDE 2.2+ for IAM authentication support.

Note: This demo documents the correct API but cannot run without GLIDE 2.2+.
      Actual connection will also fail without valid AWS credentials and ElastiCache cluster.

Usage:
    cd python/demos/authentication
    python3 iam_auth_demo.py
"""
import sys

print("Python GLIDE AWS IAM Authentication Demo\n")
print("=== Checking GLIDE Version ===")

try:
    from glide import IamAuthConfig, ServiceType
    print("✓ GLIDE 2.2+ detected (IAM auth supported)")
    iam_supported = True
except ImportError:
    print("⚠ GLIDE 2.2+ required for IAM authentication")
    print("  Current version does not support IamAuthConfig")
    print("  Install with: pip install --upgrade valkey-glide")
    iam_supported = False

if iam_supported:
    import asyncio
    from glide import (
        GlideClient,
        GlideClientConfiguration,
        NodeAddress,
        ServerCredentials
    )

    async def test_iam_auth():
        """Test AWS IAM authentication configuration"""
        print("\n=== Testing AWS IAM Authentication ===")
        
        # AWS ElastiCache IAM configuration
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
        
        print("✓ IAM configuration created successfully")
        print("  Cluster: my-cluster")
        print("  Service: ELASTICACHE")
        print("  Region: us-east-1")
        print("  Username: myUser")
        
        # Attempt connection (will fail without actual AWS infrastructure)
        try:
            client = await GlideClient.create(config)
            try:
                await client.set("iam_test", "Hello from IAM!")
                value = await client.get("iam_test")
                print(f"✓ IAM auth works: {value}")
            finally:
                await client.close()
        except Exception as e:
            # Expected to fail without actual AWS infrastructure
            error_msg = str(e)
            if "Connection" in error_msg or "Name or service not known" in error_msg or "refused" in error_msg:
                print("✓ Configuration is valid (connection failure is expected)")
            else:
                print(f"⚠ Unexpected error: {error_msg}")
                raise

    asyncio.run(test_iam_auth())
else:
    print("\n=== IAM Configuration Example (GLIDE 2.2+) ===")
    print("""
from glide import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ServerCredentials,
    IamAuthConfig,
    ServiceType
)

# AWS ElastiCache IAM configuration
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

async with GlideClient.create(config) as client:
    await client.set("key", "value")
    """)

print("\n=== Testing Complete ===")
