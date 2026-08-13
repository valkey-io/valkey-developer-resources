import Redis from "ioredis";

const client = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });

try {
  const pong = await client.ping();
  console.log(`PING → ${pong}`);

  const info = await client.call("INFO", "SERVER");
  const serverName = info.match(/^server_name:(.+)$/m)?.[1]?.trim();
  const version = info.match(/^(?:valkey_version|redis_version):(.+)$/m)?.[1]?.trim();

  if (serverName === "valkey") {
    console.log(`Backend: Valkey ${version}`);
  } else {
    console.log(`Backend: Non-Valkey server (server_name=${serverName ?? "unknown"}, version=${version ?? "unknown"})`);
  }
} catch (err) {
  console.error("Health check failed:", err.message);
  process.exitCode = 1;
} finally {
  client.disconnect();
}
