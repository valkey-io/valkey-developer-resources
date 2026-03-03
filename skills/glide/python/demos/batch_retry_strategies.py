"""
Batch Operations with Retry Strategies Demo

Demonstrates when to use retryServerError, retryConnectionError, and when to avoid both.
"""

import asyncio
import os
from glide import GlideClusterClient, GlideClusterClientConfiguration, NodeAddress, ClusterBatchOptions, ClusterBatch
from glide_shared.commands.batch_options import BatchRetryStrategy

async def demo_retry_strategies():
    """Demonstrate different retry strategy scenarios."""
    
    host = os.getenv("VALKEY_HOST", "localhost")
    
    config = GlideClusterClientConfiguration(
        addresses=[
            NodeAddress(host, 7000),
            NodeAddress(host, 7001),
            NodeAddress(host, 7002),
        ],
        request_timeout=5000,
    )
    
    client = await GlideClusterClient.create(config)
    
    try:
        print("=== Batch Operation Retry Strategies ===\n")
        
        # Scenario 1: retryServerError - Cluster resharding/server load
        print("1. RETRY SERVER ERRORS (cluster resharding, server under load)")
        print("   Use when: Transient server errors, TRYAGAIN responses")
        print("   Trade-off: May reorder commands within batch\n")
        
        batch = ClusterBatch(is_atomic=False)
        batch.set("{user:1}:name", "Alice")
        batch.set("{user:1}:email", "alice@example.com")
        batch.get("{user:1}:name")
        
        options = ClusterBatchOptions(
            retry_strategy=BatchRetryStrategy(
                retry_server_error=True,  # Retry on TRYAGAIN
                retry_connection_error=False,
            )
        )
        
        results = await client.exec(batch, raise_on_error=True, options=options)
        print(f"   ✓ Results: {results}\n")
        
        # Scenario 2: retryConnectionError - Network instability
        print("2. RETRY CONNECTION ERRORS (network instability, failover)")
        print("   Use when: Network issues, cluster node failover")
        print("   Trade-off: May duplicate entire batch\n")
        
        batch = ClusterBatch(is_atomic=False)
        batch.set("{user:2}:name", "Bob")
        batch.set("{user:2}:email", "bob@example.com")
        batch.get("{user:2}:name")
        
        options = ClusterBatchOptions(
            retry_strategy=BatchRetryStrategy(
                retry_server_error=False,
                retry_connection_error=True,  # Retry on connection loss
            )
        )
        
        results = await client.exec(batch, raise_on_error=True, options=options)
        print(f"   ✓ Results: {results}\n")
        
        # Scenario 3: Both retries - Maximum resilience
        print("3. RETRY BOTH (maximum resilience)")
        print("   Use when: High availability required, idempotent operations")
        print("   Trade-off: Possible reordering + duplication\n")
        
        batch = ClusterBatch(is_atomic=False)
        batch.set("{user:3}:name", "Charlie")
        batch.set("{user:3}:email", "charlie@example.com")
        batch.get("{user:3}:name")
        
        options = ClusterBatchOptions(
            retry_strategy=BatchRetryStrategy(
                retry_server_error=True,
                retry_connection_error=True,
            )
        )
        
        results = await client.exec(batch, raise_on_error=True, options=options)
        print(f"   ✓ Results: {results}\n")
        
        # Scenario 4: No retries - Strict latency requirements
        print("4. NO RETRIES (strict latency, non-idempotent)")
        print("   Use when: SLA-bound operations, already have app-level retry")
        print("   Trade-off: Fail fast on any error\n")
        
        batch = ClusterBatch(is_atomic=False)
        batch.set("{user:4}:name", "Diana")
        batch.set("{user:4}:email", "diana@example.com")
        batch.get("{user:4}:name")
        
        options = ClusterBatchOptions(
            retry_strategy=BatchRetryStrategy(
                retry_server_error=False,
                retry_connection_error=False,
            )
        )
        
        results = await client.exec(batch, raise_on_error=True, options=options)
        print(f"   ✓ Results: {results}\n")
        
        print("=== Summary ===")
        print("✓ retryServerError: Cluster resharding, server load")
        print("✓ retryConnectionError: Network issues, failover")
        print("✓ Both: Maximum resilience (idempotent ops)")
        print("✓ Neither: Strict latency, non-idempotent, app-level retry")
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(demo_retry_strategies())
