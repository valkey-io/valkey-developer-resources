import { createClient } from "redis";

async function main() {
  const client = createClient({ url: "redis://localhost:6379" });
  client.on("error", (err) => {
    console.error("❌ Connection error:", err.message);
    process.exit(1);
  });

  await client.connect();

  try {
    const pong = await client.ping();
    console.log(`PING: ${pong}`);

    const info = await client.info("server");
    const versionMatch = info.match(/valkey_version:(.+)/);
    if (versionMatch) {
      console.log(`Valkey version: ${versionMatch[1].trim()}`);
    }

    console.log("\n✅ Health check passed — Valkey is ready.");
  } finally {
    await client.quit();
  }
}

main().catch((err) => {
  console.error("❌ Health check failed:", err.message);
  process.exit(1);
});
