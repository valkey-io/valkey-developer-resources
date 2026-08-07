import { GlideClient } from "@valkey/valkey-glide";

async function main() {
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });

  try {
    // Basic connectivity
    const pong = await client.ping();
    console.log(`PING: ${pong}`);

    // Confirm search module is loaded
    const result = await client.customCommand(["FT._LIST"]);
    console.log(`FT._LIST: ${JSON.stringify(result)} (search module available)`);

    console.log("\n✅ Health check passed — Valkey is ready with search module.");
  } finally {
    client.close();
  }
}

main().catch((err) => {
  console.error("❌ Health check failed:", err.message);
  process.exitCode = 1;
});
