/**
 * Health check script for Valkey connectivity using @valkey/valkey-glide.
 * Mirrors how Recall's ValkeyClientProvider checks the connection.
 */
import { GlideClient } from "@valkey/valkey-glide";

const VALKEY_HOST = process.env.VALKEY_HOST || "localhost";
const VALKEY_PORT = Number(process.env.VALKEY_PORT) || 6379;

async function main() {
  console.log(`Connecting to Valkey at ${VALKEY_HOST}:${VALKEY_PORT}...`);

  let client;
  try {
    client = await GlideClient.createClient({
      addresses: [{ host: VALKEY_HOST, port: VALKEY_PORT }],
    });

    const result = await client.ping();
    if (result === "PONG") {
      console.log("✓ Valkey is healthy — PONG received");
      process.exit(0);
    } else {
      console.error(`✗ Unexpected response: ${result}`);
      process.exit(1);
    }
  } catch (error) {
    console.error(`✗ Connection failed: ${error.message}`);
    process.exit(1);
  } finally {
    if (client) {
      client.close();
    }
  }
}

main();
