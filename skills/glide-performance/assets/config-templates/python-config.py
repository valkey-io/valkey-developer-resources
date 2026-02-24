# Python GLIDE Configuration Template
# Optimized for production web applications

from glide import (
    GlideClient,
    GlideClusterClient,
    GlideClientConfiguration,
    GlideClusterClientConfiguration,
    NodeAddress,
    BackoffStrategy,
    ReadFrom,
)

# Standalone Client Configuration (Async)
async_standalone_config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    
    # Request timeout (500ms recommended for web apps)
    request_timeout=500,
    
    # Connection retry strategy
    reconnect_strategy=BackoffStrategy(
        num_of_retries=10,
        factor=500,        # Base delay in ms
        exponent_base=2,   # Exponential backoff
    ),
    
    # Client name for debugging
    client_name="my-app-client",
    
    # Lazy connect for serverless/Lambda
    lazy_connect=False,  # Set to True for Lambda
    
    # High-throughput configuration
    inflight_requests_limit=2000,  # Default: 1000
)

# Cluster Client Configuration (Async)
async_cluster_config = GlideClusterClientConfiguration(
    addresses=[NodeAddress("cluster.endpoint.cache.amazonaws.com", 6379)],
    
    # Request timeout
    request_timeout=500,
    
    # AZ Affinity for cost optimization (read-heavy workloads)
    read_from=ReadFrom.AZ_AFFINITY,
    client_az="us-east-1a",  # Your application's AZ
    
    # Connection retry strategy
    reconnect_strategy=BackoffStrategy(
        num_of_retries=10,
        factor=500,
        exponent_base=2,
    ),
    
    # Client name
    client_name="my-app-cluster-client",
    
    # High-throughput configuration
    inflight_requests_limit=2000,
)

# Create clients (do this once at application startup)
async def create_async_clients():
    standalone = await GlideClient.create(async_standalone_config)
    cluster = await GlideClusterClient.create(async_cluster_config)
    return standalone, cluster

# Graceful shutdown
async def close_async_clients(standalone, cluster):
    await standalone.close()
    await cluster.close()

# Sync Client Configuration
# The sync client is a separate package: pip install valkey-glide-sync
# Note: In your application, use either async (glide) or sync (glide_sync), not both.
# Both are shown here for reference. The glide_sync module exports the same class names
# (GlideClient, GlideClientConfiguration, NodeAddress), aliased here to avoid collision.
from glide_sync import GlideClient as GlideClientSync

sync_standalone_config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
    reconnect_strategy=BackoffStrategy(
        num_of_retries=10,
        factor=500,
        exponent_base=2,
    ),
    client_name="my-app-sync-client",
)

# Create sync client
def create_sync_client():
    standalone = GlideClientSync.create(sync_standalone_config)
    return standalone

# Graceful shutdown
def close_sync_client(standalone):
    standalone.close()
