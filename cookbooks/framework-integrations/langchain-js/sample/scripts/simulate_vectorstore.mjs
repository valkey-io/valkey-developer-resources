import { GlideClient, GlideFt } from "@valkey/valkey-glide";

const INDEX_NAME = "idx:simulate_vectorstore";
const PREFIX = "doc:simulate:";
const VECTOR_DIM = 4;

function vectorToBuffer(vector) {
  return Buffer.from(new Float32Array(vector).buffer);
}

async function main() {
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });

  try {
    // Clean up any previous run
    try {
      await GlideFt.dropindex(client, INDEX_NAME);
    } catch {
      // Index may not exist
    }

    // 1. Create index (HASH schema with VECTOR + TAG fields)
    console.log("Creating index...");
    await GlideFt.create(client, INDEX_NAME, [
      {
        type: "VECTOR",
        name: "embedding",
        alias: "embedding",
        attributes: {
          algorithm: "HNSW",
          distanceMetric: "COSINE",
          type: "FLOAT32",
          dimensions: VECTOR_DIM,
        },
      },
      {
        type: "TAG",
        name: "category",
        alias: "category",
      },
    ], {
      dataType: "HASH",
      prefixes: [PREFIX],
    });
    console.log(`Index "${INDEX_NAME}" created.`);

    // 2. Store documents as hashes with vector embeddings
    // Note: customCommand is used for HSET to preserve raw binary vector data.
    // The typed hset() method re-encodes values as UTF-8, which corrupts binary vectors.
    const documents = [
      { id: "1", text: "Valkey is fast", category: "database", embedding: [1.0, 0.0, 0.0, 0.0] },
      { id: "2", text: "LangChain is useful", category: "framework", embedding: [0.0, 1.0, 0.0, 0.0] },
      { id: "3", text: "Vectors enable search", category: "database", embedding: [0.9, 0.1, 0.0, 0.0] },
    ];

    console.log("Storing documents...");
    for (const doc of documents) {
      await client.customCommand([
        "HSET", `${PREFIX}${doc.id}`,
        "text", doc.text,
        "category", doc.category,
        "embedding", vectorToBuffer(doc.embedding),
      ]);
    }
    console.log(`Stored ${documents.length} documents.`);

    // Allow time for indexing
    await new Promise((resolve) => setTimeout(resolve, 300));

    // 3. KNN search — find nearest to [1.0, 0.0, 0.0, 0.0]
    console.log("\nSearching for nearest neighbors...");
    const queryVector = vectorToBuffer([1.0, 0.0, 0.0, 0.0]);

    const results = await GlideFt.search(
      client,
      INDEX_NAME,
      "*=>[KNN 2 @embedding $BLOB AS score]",
      {
        params: [{ key: "BLOB", value: queryVector }],
        returnFields: [
          { fieldIdentifier: "text" },
          { fieldIdentifier: "category" },
          { fieldIdentifier: "score" },
        ],
      },
    );

    const [totalCount, matches] = results;
    console.log(`Found ${totalCount} results:`);
    for (const match of matches) {
      const fields = Object.fromEntries(match.value.map((f) => [f.key, f.value]));
      console.log(`  - ${match.key}: "${fields.text}" (score: ${fields.score}, category: ${fields.category})`);
    }

    // 4. Cleanup
    console.log("\nCleaning up...");
    await GlideFt.dropindex(client, INDEX_NAME);
    for (const doc of documents) {
      await client.del([`${PREFIX}${doc.id}`]);
    }
    console.log("✅ Simulation complete.");
  } finally {
    client.close();
  }
}

main().catch((err) => {
  console.error("❌ Simulation failed:", err.message);
  process.exit(1);
});
