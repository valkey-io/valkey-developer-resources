const { GlideClient, Batch } = require("@valkey/valkey-glide");

// Production-optimized configuration
const productionConfig = {
  addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
  requestTimeout: 500,
  connectionBackoff: {
    numberOfRetries: 10,
    factor: 500,
    exponentBase: 2,
  },
  clientName: "bulk-demo",
  inflightRequestsLimit: 2000,
};

async function bulkDemo() {
  const client = await GlideClient.createClient(productionConfig);

  try {
    const keyCount = 5000;
    const batchSize = 100;

    // Write thousands of keys efficiently
    console.log(`Writing ${keyCount} keys in batches of ${batchSize}...`);
    const writeStart = Date.now();

    for (let i = 0; i < keyCount; i += batchSize) {
      const batch = new Batch(false);
      for (let j = 0; j < batchSize && i + j < keyCount; j++) {
        batch.set(`key:${i + j}`, `value-${i + j}`);
      }
      await client.exec(batch, true);
    }

    const writeTime = Date.now() - writeStart;
    console.log(`✓ Wrote ${keyCount} keys in ${writeTime}ms (${Math.round(keyCount / (writeTime / 1000))} ops/sec)`);

    // Read thousands of keys efficiently
    console.log(`\nReading ${keyCount} keys in batches of ${batchSize}...`);
    const readStart = Date.now();

    for (let i = 0; i < keyCount; i += batchSize) {
      const batch = new Batch(false);
      for (let j = 0; j < batchSize && i + j < keyCount; j++) {
        batch.get(`key:${i + j}`);
      }
      await client.exec(batch, true);
    }

    const readTime = Date.now() - readStart;
    console.log(`✓ Read ${keyCount} keys in ${readTime}ms (${Math.round(keyCount / (readTime / 1000))} ops/sec)`);

    // Cleanup
    console.log(`\nCleaning up ${keyCount} keys...`);
    for (let i = 0; i < keyCount; i += batchSize) {
      const batch = new Batch(false);
      const keys = [];
      for (let j = 0; j < batchSize && i + j < keyCount; j++) {
        keys.push(`key:${i + j}`);
      }
      batch.del(keys);
      await client.exec(batch, true);
    }
    console.log("✓ Cleanup complete");

  } finally {
    client.close();
  }
}

bulkDemo().catch(console.error);
