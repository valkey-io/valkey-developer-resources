const { GlideClusterClient, ClusterBatch } = require("@valkey/valkey-glide");

async function main() {
    const host = process.env.VALKEY_HOST || "localhost";
    
    const client = await GlideClusterClient.createClient({
        addresses: [
            { host, port: 7000 },
            { host, port: 7001 },
            { host, port: 7002 },
        ],
        requestTimeout: 10000,
    });

    try {
        console.log("=== Batch Operation Retry Strategies ===\n");

        // Scenario 1: retryServerError - Cluster resharding/server load
        console.log("1. RETRY SERVER ERRORS (cluster resharding, server under load)");
        console.log("   Use when: Transient server errors, TRYAGAIN responses");
        console.log("   Trade-off: May reorder commands within batch\n");

        const batch1 = new ClusterBatch(false);
        batch1.set("{user:1}:name", "Alice");
        batch1.set("{user:1}:email", "alice@example.com");
        batch1.get("{user:1}:name");

        const options1 = {
            retryStrategy: {
                retryServerError: true,
                retryConnectionError: false,
            },
        };

        const results1 = await client.exec(batch1, true, options1);
        console.log(`   ✓ Results: ${JSON.stringify(results1)}\n`);

        // Scenario 2: retryConnectionError - Network instability
        console.log("2. RETRY CONNECTION ERRORS (network instability, failover)");
        console.log("   Use when: Network issues, cluster node failover");
        console.log("   Trade-off: May duplicate entire batch\n");

        const batch2 = new ClusterBatch(false);
        batch2.set("{user:2}:name", "Bob");
        batch2.set("{user:2}:email", "bob@example.com");
        batch2.get("{user:2}:name");

        const options2 = {
            retryStrategy: {
                retryServerError: false,
                retryConnectionError: true,
            },
        };

        const results2 = await client.exec(batch2, true, options2);
        console.log(`   ✓ Results: ${JSON.stringify(results2)}\n`);

        // Scenario 3: Both retries - Maximum resilience
        console.log("3. RETRY BOTH (maximum resilience)");
        console.log("   Use when: High availability required, idempotent operations");
        console.log("   Trade-off: Possible reordering + duplication\n");

        const batch3 = new ClusterBatch(false);
        batch3.set("{user:3}:name", "Charlie");
        batch3.set("{user:3}:email", "charlie@example.com");
        batch3.get("{user:3}:name");

        const options3 = {
            retryStrategy: {
                retryServerError: true,
                retryConnectionError: true,
            },
        };

        const results3 = await client.exec(batch3, true, options3);
        console.log(`   ✓ Results: ${JSON.stringify(results3)}\n`);

        // Scenario 4: No retries - Strict latency requirements
        console.log("4. NO RETRIES (strict latency, non-idempotent)");
        console.log("   Use when: SLA-bound operations, already have app-level retry");
        console.log("   Trade-off: Fail fast on any error\n");

        const batch4 = new ClusterBatch(false);
        batch4.set("{user:4}:name", "Diana");
        batch4.set("{user:4}:email", "diana@example.com");
        batch4.get("{user:4}:name");

        const options4 = {
            retryStrategy: {
                retryServerError: false,
                retryConnectionError: false,
            },
        };

        const results4 = await client.exec(batch4, true, options4);
        console.log(`   ✓ Results: ${JSON.stringify(results4)}\n`);

        console.log("=== Summary ===");
        console.log("✓ retryServerError: Cluster resharding, server load");
        console.log("✓ retryConnectionError: Network issues, failover");
        console.log("✓ Both: Maximum resilience (idempotent ops)");
        console.log("✓ Neither: Strict latency, non-idempotent, app-level retry");
    } finally {
        client.close();
    }
}

main().catch(console.error);
