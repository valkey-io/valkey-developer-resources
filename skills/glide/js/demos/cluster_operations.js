const { GlideClusterClient, ClusterBatch } = require("@valkey/valkey-glide");

async function main() {
    const client = await GlideClusterClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST, port: 7000 }],
        requestTimeout: 10000,
    });

    try {
        console.log("Connected to cluster");

        // Hash tags ensure same slot: {user}:1 and {user}:2
        const atomicBatch = new ClusterBatch(true);
        atomicBatch.set("{user}:1", "Alice");
        atomicBatch.set("{user}:2", "Bob");
        atomicBatch.get("{user}:1");

        const results = await client.exec(atomicBatch, true);
        console.log("Atomic batch (same slot):", results);

        // Atomic batch with different slots fails with CROSSSLOT
        const crossSlotBatch = new ClusterBatch(true);
        crossSlotBatch.set("key1", "value1");
        crossSlotBatch.set("key2", "value2");

        try {
            await client.exec(crossSlotBatch, true);
            console.log("ERROR: Should have failed with CROSSSLOT");
        } catch (err) {
            console.log("Expected CROSSSLOT error:", err.message);
        }

        // Non-atomic batch can span multiple slots
        const pipelineBatch = new ClusterBatch(false);
        pipelineBatch.set("key1", "value1");
        pipelineBatch.set("key2", "value2");
        pipelineBatch.get("key1");
        pipelineBatch.get("key2");

        const pipelineResults = await client.exec(pipelineBatch, true);
        console.log("Pipeline (multi-slot):", pipelineResults);

        // Cleanup using non-atomic batch for multi-slot delete
        const cleanupBatch = new ClusterBatch(false);
        cleanupBatch.del(["{user}:1", "{user}:2"]);
        cleanupBatch.del(["key1"]);
        cleanupBatch.del(["key2"]);

        const cleanupResults = await client.exec(cleanupBatch, true);
        console.log("Cleanup batch results:", cleanupResults);
        console.log("Cluster operations completed");
    } finally {
        client.close();
    }
}

main().catch(console.error);
