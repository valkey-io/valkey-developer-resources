const { GlideClient, GlideFt, Decoder } = require("@valkey/valkey-glide");

async function vectorSearchDemo() {
  const client = await GlideClient.createClient({
    addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
  });

  try {
    const indexName = "products_idx";
    const keyPrefix = "product:";

    // Cleanup
    try {
      await GlideFt.dropindex(client, indexName);
      await client.del(["product:1", "product:2"]);
    } catch (e) {}

    // Create index with vector field
    await GlideFt.create(
      client,
      indexName,
      [
        {
          name: "description_vector",
          alias: "vector",
          type: "VECTOR",
          attributes: {
            algorithm: "HNSW",
            type: "FLOAT32",
            dimensions: 3,
            distanceMetric: "L2",
          },
        },
      ],
      { dataType: "HASH", prefixes: [keyPrefix] }
    );

    // Add documents with vectors
    const vector1 = Buffer.from(new Float32Array([1.0, 2.0, 3.0]).buffer);
    const vector2 = Buffer.from(new Float32Array([4.0, 5.0, 6.0]).buffer);

    await client.hset("product:1", { name: "Product A", description_vector: vector1 });
    await client.hset("product:2", { name: "Product B", description_vector: vector2 });

    // Vector search
    const queryVector = Buffer.from(new Float32Array([1.5, 2.5, 3.5]).buffer);
    const results = await GlideFt.search(client, indexName, `*=>[KNN 2 @vector $vec]`, {
      params: [{ key: "vec", value: queryVector }],
      returnAttributes: ["name"],
      decoder: Decoder.Bytes,
    });

    console.log("Vector search results:", results);

    // Cleanup
    await GlideFt.dropindex(client, indexName);
    await client.del(["product:1", "product:2"]);
  } catch (error) {
    console.error("Error:", error.message);
  } finally {
    client.close();
  }
}

vectorSearchDemo();
