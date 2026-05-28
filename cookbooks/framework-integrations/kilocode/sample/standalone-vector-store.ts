/**
 * standalone-vector-store.ts
 *
 * Minimal standalone example using the same GLIDE patterns Kilocode uses internally:
 * create an HNSW index, upsert vectors with TAG fields, and search with KNN.
 *
 * This demonstrates the underlying mechanics — you don't need to run this to use
 * Kilocode. All indexing happens automatically through the Kilocode UI/CLI.
 *
 * Usage: npx tsx standalone-vector-store.ts
 */

import { GlideClient, GlideFt, Batch } from "@valkey/valkey-glide";
import type { Field, FtCreateOptions, GlideString } from "@valkey/valkey-glide";

const COLLECTION = "demo_index";
const DIMS = 384;

function encodeVector(vector: number[]): Buffer {
  const buffer = Buffer.alloc(vector.length * 4);
  for (let i = 0; i < vector.length; i++) {
    buffer.writeFloatLE(vector[i], i * 4);
  }
  return buffer;
}

function randomVector(dims: number): number[] {
  return Array.from({ length: dims }, () => Math.random() * 2 - 1);
}

function splitPathSegments(filePath: string): Record<string, string> {
  const segments = filePath.split("/").filter(Boolean);
  const result: Record<string, string> = {};
  const maxSegments = Math.min(segments.length, 5);
  for (let i = 0; i < maxSegments; i++) {
    result[`seg${i}`] = segments[i];
  }
  return result;
}

// Sample code chunks with file paths (mimics what Kilocode stores)
const chunks = [
  {
    id: "001",
    filePath: "src/auth/login.ts",
    codeChunk: "async function login()",
    startLine: 1,
    endLine: 20,
  },
  {
    id: "002",
    filePath: "src/auth/signup.ts",
    codeChunk: "async function signup()",
    startLine: 1,
    endLine: 15,
  },
  {
    id: "003",
    filePath: "src/utils/hash.ts",
    codeChunk: "function hashPassword()",
    startLine: 5,
    endLine: 12,
  },
  {
    id: "004",
    filePath: "src/utils/validate.ts",
    codeChunk: "function validateEmail()",
    startLine: 1,
    endLine: 8,
  },
  {
    id: "005",
    filePath: "tests/auth/login.test.ts",
    codeChunk: "describe('login')",
    startLine: 1,
    endLine: 30,
  },
];

async function main() {
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    clientName: "cookbook-demo",
    requestTimeout: 5000,
  });

  try {
    console.log("Connected to Valkey\n");

    // Drop existing index if present
    try {
      await GlideFt.dropindex(client, COLLECTION);
      console.log("Dropped existing index.");
    } catch {
      // Index doesn't exist — fine
    }

    // Clean up any orphaned keys from previous runs
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${COLLECTION}:*`,
        count: 100,
      });
      cursor = String(nextCursor);
      if (keys.length > 0) {
        await client.del(keys as string[]);
      }
    } while (cursor !== "0");

    // Create index — same schema Kilocode uses
    const schema: Field[] = [
      {
        type: "VECTOR",
        name: "vector",
        attributes: {
          algorithm: "HNSW",
          type: "FLOAT32",
          dimensions: DIMS,
          distanceMetric: "COSINE",
        },
      },
      { type: "TAG", name: "seg0" },
      { type: "TAG", name: "seg1" },
      { type: "TAG", name: "seg2" },
      { type: "TAG", name: "seg3" },
      { type: "TAG", name: "seg4" },
      { type: "TAG", name: "filePath", separator: "\x00" },
      { type: "TAG", name: "type" },
    ];

    const options: FtCreateOptions = {
      dataType: "HASH",
      prefixes: [`${COLLECTION}:`],
    };

    await GlideFt.create(client, COLLECTION, schema, options);
    console.log(
      `Created index "${COLLECTION}" (HNSW, COSINE, FLOAT32, ${DIMS} dims)\n`,
    );

    // Batch upsert — same pattern Kilocode uses (non-atomic pipeline)
    const vectors = chunks.map(() => randomVector(DIMS));
    const batch = new Batch(false);

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const key = `${COLLECTION}:${chunk.id}`;
      const fields: Record<string, GlideString> = {
        vector: encodeVector(vectors[i]),
        filePath: chunk.filePath,
        codeChunk: chunk.codeChunk,
        startLine: String(chunk.startLine),
        endLine: String(chunk.endLine),
        type: "point",
        ...splitPathSegments(chunk.filePath),
      };
      batch.hset(key, fields);
    }

    await client.exec(batch, true);
    console.log(`Upserted ${chunks.length} vectors\n`);

    // Wait for indexing
    await new Promise((r) => setTimeout(r, 500));

    // KNN search — all points
    const queryVector = encodeVector(vectors[0]);
    const query = "(@type:{point})=>[KNN 3 @vector $BLOB AS score]";

    const [count, documents] = await GlideFt.search(client, COLLECTION, query, {
      params: [{ key: "BLOB", value: queryVector }],
      returnFields: [
        { fieldIdentifier: "filePath" },
        { fieldIdentifier: "codeChunk" },
        { fieldIdentifier: "score" },
      ],
      dialect: 2,
      limit: { offset: 0, count: 3 },
    });

    console.log(`KNN search (top 3, all paths) — ${count} total matches:`);
    if (Array.isArray(documents)) {
      for (const doc of documents) {
        console.log(`  ${doc.key}`);
      }
    }

    // Filtered search — only src/auth/
    const filteredQuery =
      "(@type:{point} @seg0:{src} @seg1:{auth})=>[KNN 3 @vector $BLOB AS score]";
    const [filteredCount, filteredDocs] = await GlideFt.search(
      client,
      COLLECTION,
      filteredQuery,
      {
        params: [{ key: "BLOB", value: queryVector }],
        returnFields: [
          { fieldIdentifier: "filePath" },
          { fieldIdentifier: "score" },
        ],
        dialect: 2,
        limit: { offset: 0, count: 3 },
      },
    );

    console.log(
      `\nFiltered search (src/auth/ only) — ${filteredCount} total matches:`,
    );
    if (Array.isArray(filteredDocs)) {
      for (const doc of filteredDocs) {
        console.log(`  ${doc.key}`);
      }
    }

    // Cleanup
    await GlideFt.dropindex(client, COLLECTION);
    cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${COLLECTION}:*`,
        count: 100,
      });
      cursor = String(nextCursor);
      if (keys.length > 0) {
        await client.del(keys as string[]);
      }
    } while (cursor !== "0");

    console.log("\nCleaned up. Done.");
  } finally {
    client.close();
  }
}

main().catch(console.error);
