const { GlideClient, Batch } = require("@valkey/valkey-glide");

async function main() {
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST, port: 6379 }],
        requestTimeout: 10000,
    });

    try {
        // Pipeline (non-atomic): bulk independent operations
        const pipeline = new Batch(false);
        pipeline.set("user:1", "Alice");
        pipeline.set("user:2", "Bob");
        pipeline.get("user:1");
        pipeline.get("user:2");

        const results = await client.exec(pipeline, true);
        console.log("Pipeline results:", results);

        // Transaction (atomic): consistent multi-key update
        const transaction = new Batch(true);
        transaction.set("counter", "0");
        transaction.incr("counter");
        transaction.incr("counter");
        transaction.get("counter");

        const txResults = await client.exec(transaction, true);
        console.log("Transaction results:", txResults);

        console.log("Batch/pipeline operations completed");
    } finally {
        client.close();
    }
}

main().catch(console.error);
