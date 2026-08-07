import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { GlideClient, GlideFt, Decoder } from "@valkey/valkey-glide";
import { vectorToBuffer, vectorFieldSchema } from "../lib/vector_utils.mjs";

const INDEX_NAME = "idx:test_vectorstore";
const PREFIX = "doc:test:";
const VECTOR_DIM = 4;

/**
 * Poll FT.INFO until all documents are indexed (indexing_failures + docs being indexed = 0).
 * Falls back to a maximum wait of 5 seconds.
 */
async function waitForIndexing(client, indexName, expectedDocs, maxWaitMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const info = await GlideFt.info(client, indexName);
      const numDocs = Number(info.num_docs ?? info.numDocs ?? 0);
      if (numDocs >= expectedDocs) return;
    } catch {
      // index may not be ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

/** Delete all keys matching the test prefix and drop the index if it exists. */
async function cleanup(client) {
  try {
    await GlideFt.dropindex(client, INDEX_NAME);
  } catch (err) {
    if (!String(err?.message ?? err).includes("Unknown index")) throw err;
  }
  let cursor = "0";
  do {
    const [nextCursor, keys] = await client.customCommand(["SCAN", cursor, "MATCH", `${PREFIX}*`, "COUNT", "100"]);
    cursor = nextCursor;
    if (keys.length > 0) {
      await client.del(keys);
    }
  } while (cursor !== "0");
}

/**
 * Store a document hash with a binary vector field.
 * Uses customCommand to bypass UTF-8 re-encoding in the typed hset() method,
 * which would corrupt raw binary vector data.
 */
async function hsetWithVector(client, key, fields) {
  const args = ["HSET", key];
  for (const [k, v] of Object.entries(fields)) {
    args.push(k, v);
  }
  await client.customCommand(args);
}

describe("ValkeyVectorStore Patterns", () => {
  let client;

  beforeEach(async () => {
    client = await GlideClient.createClient({
      addresses: [{ host: "localhost", port: 6379 }],
    });
    await cleanup(client);
  });

  afterEach(async () => {
    if (client) {
      await cleanup(client);
      client.close();
      client = null;
    }
  });

  describe("Connectivity", () => {
    it("should respond to PING", async () => {
      const result = await client.ping();
      assert.equal(result, "PONG");
    });

    it("should have search module loaded (FT._LIST)", async () => {
      const result = await client.customCommand(["FT._LIST"]);
      assert.ok(Array.isArray(result), "FT._LIST should return an array");
    });
  });

  describe("Index Lifecycle", () => {
    it("should create and drop an index", async () => {
      await GlideFt.create(client, INDEX_NAME, [
        vectorFieldSchema({ dimensions: VECTOR_DIM }),
      ], {
        dataType: "HASH",
        prefixes: [PREFIX],
      });

      // Verify index exists via FT.INFO
      const info = await GlideFt.info(client, INDEX_NAME);
      assert.ok(info, "FT.INFO should return index metadata");

      // Drop index
      await GlideFt.dropindex(client, INDEX_NAME);

      // Verify index is gone
      await assert.rejects(
        async () => GlideFt.info(client, INDEX_NAME),
        "FT.INFO should fail after drop",
      );
    });

    it("should appear in FT._LIST after creation", async () => {
      await GlideFt.create(client, INDEX_NAME, [
        vectorFieldSchema({ dimensions: VECTOR_DIM }),
      ], {
        dataType: "HASH",
        prefixes: [PREFIX],
      });

      const indices = await client.customCommand(["FT._LIST"]);
      assert.ok(indices.includes(INDEX_NAME), `Expected ${INDEX_NAME} in index list`);
    });
  });

  describe("Document Storage", () => {
    it("should store and retrieve a document with vector embedding", async () => {
      const vector = [0.5, 0.3, 0.1, 0.8];
      const vectorBuf = vectorToBuffer(vector);

      await hsetWithVector(client, `${PREFIX}1`, {
        text: "Hello world",
        category: "greeting",
        embedding: vectorBuf,
      });

      // Retrieve text fields with HGET (hgetall fails on binary vector data)
      const text = await client.hget(`${PREFIX}1`, "text");
      const category = await client.hget(`${PREFIX}1`, "category");
      assert.equal(text, "Hello world");
      assert.equal(category, "greeting");

      // Verify vector field exists and has correct length via customCommand with Decoder.Bytes
      const rawVec = await client.customCommand(
        ["HGET", `${PREFIX}1`, "embedding"],
        { decoder: Decoder.Bytes },
      );
      assert.ok(rawVec, "embedding field should exist");
      // rawVec is a Buffer; verify byte length matches VECTOR_DIM * 4 (Float32)
      assert.equal(rawVec.length, VECTOR_DIM * 4, `Expected ${VECTOR_DIM * 4} bytes for vector`);

      // Verify vector round-trip
      const retrieved = new Float32Array(new Uint8Array(rawVec).buffer);
      assert.equal(retrieved.length, VECTOR_DIM);
      assert.ok(Math.abs(retrieved[0] - 0.5) < 0.001);
      assert.ok(Math.abs(retrieved[3] - 0.8) < 0.001);
    });

    it("should store multiple documents", async () => {
      for (let i = 1; i <= 5; i++) {
        await hsetWithVector(client, `${PREFIX}${i}`, {
          text: `Document ${i}`,
          embedding: vectorToBuffer([i * 0.1, 0, 0, 0]),
        });
      }

      // Verify all stored (read text fields only to avoid binary decode issues)
      for (let i = 1; i <= 5; i++) {
        const text = await client.hget(`${PREFIX}${i}`, "text");
        assert.equal(text, `Document ${i}`);
      }
    });
  });

  describe("KNN Search", () => {
    it("should return nearest neighbors in order", async () => {
      // Create index
      await GlideFt.create(client, INDEX_NAME, [
        vectorFieldSchema({ dimensions: VECTOR_DIM }),
        {
          type: "TAG",
          name: "label",
          alias: "label",
        },
      ], {
        dataType: "HASH",
        prefixes: [PREFIX],
      });

      // Store 3 documents with different vectors
      const docs = [
        { id: "1", label: "close", embedding: [1.0, 0.0, 0.0, 0.0] },
        { id: "2", label: "far", embedding: [0.0, 1.0, 0.0, 0.0] },
        { id: "3", label: "closest", embedding: [0.95, 0.05, 0.0, 0.0] },
      ];

      for (const doc of docs) {
        await hsetWithVector(client, `${PREFIX}${doc.id}`, {
          label: doc.label,
          embedding: vectorToBuffer(doc.embedding),
        });
      }

      // Wait for indexing to complete
      await waitForIndexing(client, INDEX_NAME, 3);

      // Search for nearest to [1.0, 0.0, 0.0, 0.0]
      const queryVector = vectorToBuffer([1.0, 0.0, 0.0, 0.0]);
      const results = await GlideFt.search(
        client,
        INDEX_NAME,
        "*=>[KNN 3 @embedding $BLOB AS score]",
        {
          params: [{ key: "BLOB", value: queryVector }],
          returnFields: [
            { fieldIdentifier: "label" },
            { fieldIdentifier: "score" },
          ],
        },
      );

      const [totalCount, matches] = results;
      assert.ok(totalCount >= 2, `Expected at least 2 results, got ${totalCount}`);

      // First result should be doc:test:1 (exact match, cosine distance = 0)
      const firstMatch = matches[0];
      const firstFields = Object.fromEntries(firstMatch.value.map((f) => [f.key, f.value]));
      const firstScore = parseFloat(firstFields.score);
      assert.ok(firstScore < 0.01, `First result should have near-zero distance, got ${firstScore}`);
      assert.equal(firstMatch.key, `${PREFIX}1`);
    });
  });

  describe("Metadata Filtering", () => {
    it("should filter search results by TAG field", async () => {
      // Create index with TAG field for filtering
      await GlideFt.create(client, INDEX_NAME, [
        vectorFieldSchema({ dimensions: VECTOR_DIM }),
        {
          type: "TAG",
          name: "category",
          alias: "category",
        },
      ], {
        dataType: "HASH",
        prefixes: [PREFIX],
      });

      // Store documents with different categories
      const docs = [
        { id: "1", category: "science", embedding: [1.0, 0.0, 0.0, 0.0] },
        { id: "2", category: "art", embedding: [0.9, 0.1, 0.0, 0.0] },
        { id: "3", category: "science", embedding: [0.8, 0.2, 0.0, 0.0] },
        { id: "4", category: "art", embedding: [0.0, 1.0, 0.0, 0.0] },
      ];

      for (const doc of docs) {
        await hsetWithVector(client, `${PREFIX}${doc.id}`, {
          category: doc.category,
          embedding: vectorToBuffer(doc.embedding),
        });
      }

      // Wait for indexing to complete
      await waitForIndexing(client, INDEX_NAME, 3);

      // Search with TAG filter — only "science" category
      const queryVector = vectorToBuffer([1.0, 0.0, 0.0, 0.0]);
      const results = await GlideFt.search(
        client,
        INDEX_NAME,
        "(@category:{science})=>[KNN 4 @embedding $BLOB AS score]",
        {
          params: [{ key: "BLOB", value: queryVector }],
          returnFields: [
            { fieldIdentifier: "category" },
            { fieldIdentifier: "score" },
          ],
        },
      );

      const [totalCount, matches] = results;
      assert.equal(totalCount, 2, `Expected 2 science docs, got ${totalCount}`);

      // All results should be category "science"
      for (const match of matches) {
        const fields = Object.fromEntries(match.value.map((f) => [f.key, f.value]));
        assert.equal(fields.category, "science", `Expected category 'science', got '${fields.category}'`);
      }
    });
  });
});
