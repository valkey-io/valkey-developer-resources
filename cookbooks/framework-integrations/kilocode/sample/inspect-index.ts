/**
 * inspect-index.ts
 *
 * Connect to Valkey and inspect a Kilocode-created index.
 * Shows FT._LIST, FT.INFO, sample HGETALL, and runs a KNN search.
 *
 * Run this AFTER Kilocode has indexed a project with Valkey as the vector store.
 * Kilocode names its indexes "ws-<hash>" where <hash> is derived from your workspace path.
 *
 * Usage: npx tsx inspect-index.ts
 */

import { GlideClient, GlideFt, Decoder } from "@valkey/valkey-glide";
import type { GlideString } from "@valkey/valkey-glide";

async function main() {
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    clientName: "cookbook-inspect",
    requestTimeout: 5000,
  });

  try {
    console.log("Connected to Valkey\n");

    // List all FT indexes — Kilocode creates indexes named "ws-<hash>"
    const indexes = await GlideFt.list(client);
    console.log("FT indexes:", indexes);

    // Find the first ws-* index (Kilocode's naming convention)
    const kiloIndex = (indexes as string[]).find((name) =>
      name.startsWith("ws-"),
    );

    if (!kiloIndex) {
      console.log("\nNo Kilocode index found (expected pattern: ws-*).");
      console.log(
        "Index your project with Kilocode first (Settings → Indexing → Valkey),",
      );
      console.log(
        "or run standalone-vector-store.ts to create a sample index.",
      );
      return;
    }

    console.log(`\nFound Kilocode index: "${kiloIndex}"`);

    // FT.INFO — index schema and stats
    const info = await GlideFt.info(client, kiloIndex);
    console.log("\nFT.INFO:", JSON.stringify(info, null, 2));

    // Check the metadata key
    const metadataKey = `${kiloIndex}:__metadata__`;
    const metadata = await client.hgetall(metadataKey);
    if (metadata && Object.keys(metadata).length > 0) {
      console.log(`\nMetadata (${metadataKey}):`);
      for (const [field, value] of Object.entries(metadata)) {
        console.log(`  ${field}: ${value}`);
      }
    }

    // Find a sample data point and HGETALL
    // NOTE: A single SCAN call may return 0 keys even when matching keys exist (COUNT is a hint).
    // For demo brevity we do a single pass; production code should iterate until cursor returns "0".
    const [, keys] = await client.scan("0", {
      match: `${kiloIndex}:*`,
      count: 10,
    });
    const dataKeys = (keys as string[]).filter((k) => k !== metadataKey);

    if (dataKeys.length > 0) {
      const sampleKey = dataKeys[0];
      // Use Decoder.Bytes to get raw Buffers — the default UTF-8 decoder corrupts
      // arbitrary bytes in FLOAT32 vectors (replaces invalid sequences with U+FFFD).
      const fields = await client.hgetall(sampleKey, {
        decoder: Decoder.Bytes,
      });
      console.log(`\nSample point (${sampleKey}):`);

      let vectorBuf: Buffer | null = null;

      for (const entry of fields as Array<{field: GlideString, value: GlideString}>) {
        const field = String(entry.field);
        const value = entry.value;
        if (field === "vector") {
          const buf = Buffer.isBuffer(value)
            ? value
            : Buffer.from(value as unknown as string, "binary");
          console.log(`  vector: [FLOAT32 x ${buf.length / 4} dims]`);
          vectorBuf = buf;
        } else {
          const displayValue = Buffer.isBuffer(value)
            ? value.toString("utf-8")
            : value;
          console.log(`  ${field}: ${displayValue}`);
        }
      }

      // Run a KNN search using the same vector (self-search, score ≈ 0 distance)
      if (vectorBuf) {
        const query = "(@type:{point})=>[KNN 5 @vector $BLOB AS score]";
        const [count, documents] = await GlideFt.search(
          client,
          kiloIndex,
          query,
          {
            params: [{ key: "BLOB", value: vectorBuf }],
            returnFields: [
              { fieldIdentifier: "filePath" },
              { fieldIdentifier: "score" },
            ],
            dialect: 2,
            limit: { offset: 0, count: 5 },
          },
        );

        console.log(`\nKNN search (top 5) — ${count} total indexed:`);
        if (Array.isArray(documents)) {
          for (const doc of documents) {
            const fields = new Map<string, GlideString>();
            for (const entry of doc.value as Array<{key: GlideString, value: GlideString}>) {
              fields.set(String(entry.key), entry.value);
            }
            const distance = parseFloat(String(fields.get("score") ?? "1"));
            const similarity = (1 - distance).toFixed(4);
            const filePath = String(fields.get("filePath") ?? doc.key);
            console.log(`  [${similarity}] ${filePath}`);
          }
        }
      }
    } else {
      console.log(
        "\nNo data points found in the index. Has Kilocode finished indexing?",
      );
    }

    console.log("\nDone.");
  } finally {
    client.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
