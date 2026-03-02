/**
 * Node.js GLIDE TLS + Authentication Test
 * 
 * Tests TLS connectivity with password authentication on port 6479.
 * 
 * Usage:
 *   export VALKEY_HOST=localhost
 *   cd js/demos/authentication
 *   node tls_auth_demo.js
 */

const { GlideClient } = require("@valkey/valkey-glide");

async function testTlsWithAuth() {
  console.log("=== Testing TLS + Authentication (Port 6479) ===");

  const host = process.env.VALKEY_HOST || "localhost";

  // For self-signed certificates (testing only)
  // ⚠️ WARNING: tlsAdvancedConfiguration.insecure disables certificate verification
  // In production, use proper CA-signed certificates
  const config = {
    addresses: [{ host, port: 6479 }],
    useTLS: true,
    credentials: { password: "mypassword" },
    advancedClientConfiguration: {
      tlsAdvancedConfiguration: {
        insecure: true  // Disable certificate verification for self-signed certs
      }
    },
    requestTimeout: 5000
  };

  const client = await GlideClient.createClient(config);

  try {
    // Test operations
    await client.set("tls_test_node", "Hello with TLS!");
    const value = await client.get("tls_test_node");
    console.log(`✓ TLS works: ${value}`);

    // Cleanup
    await client.del(["tls_test_node"]);
  } finally {
    client.close();
  }

  console.log("\n=== Testing Complete ===");
}

async function main() {
  console.log("Node.js GLIDE TLS + Authentication Testing\n");

  try {
    await testTlsWithAuth();
  } catch (error) {
    console.error(`✗ TLS test error: ${error.message}`);
    process.exit(1);
  }
}

main();
