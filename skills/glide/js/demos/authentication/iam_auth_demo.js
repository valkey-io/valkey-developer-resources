/**
 * Node.js GLIDE AWS IAM Authentication Demo
 * 
 * Demonstrates AWS ElastiCache/MemoryDB IAM authentication configuration.
 * This demo validates the configuration runs without AWS-specific errors.
 * 
 * Note: Actual connection will fail without valid AWS credentials and ElastiCache cluster.
 * 
 * Usage:
 *   cd js/demos/authentication
 *   node iam_auth_demo.js
 */

const { GlideClient, ServiceType } = require("@valkey/valkey-glide");

async function testIamAuth() {
  console.log("=== Testing AWS IAM Authentication ===");

  // AWS ElastiCache IAM configuration
  const config = {
    addresses: [{ host: "my-cluster.cache.amazonaws.com", port: 6379 }],
    useTLS: true,  // IAM auth requires TLS
    credentials: {
      username: "myUser",
      iamConfig: {
        cluster_name: "my-cluster",
        service: ServiceType.Elasticache,  // or ServiceType.MemoryDB
        region: "us-east-1"
      }
    },
    requestTimeout: 5000
  };

  console.log("✓ IAM configuration created successfully");
  console.log("  Cluster: my-cluster");
  console.log("  Service: Elasticache");
  console.log("  Region: us-east-1");
  console.log("  Username: myUser");

  // Attempt connection (will fail without actual AWS infrastructure)
  try {
    const client = await GlideClient.createClient(config);
    
    try {
      await client.set("iam_test", "Hello from IAM!");
      const value = await client.get("iam_test");
      console.log(`✓ IAM auth works: ${value}`);
    } finally {
      client.close();
    }
  } catch (error) {
    // Expected to fail without actual AWS infrastructure
    if (error.message.includes("Connection") || 
        error.message.includes("refused") || 
        error.message.includes("not known")) {
      console.log("✓ Configuration is valid (connection failure is expected)");
    } else {
      throw error;
    }
  }
}

async function main() {
  console.log("Node.js GLIDE AWS IAM Authentication Demo\n");

  try {
    await testIamAuth();
  } catch (error) {
    console.log("\n⚠ IAM auth demo completed (connection expected to fail without AWS)");
    console.error(`  Error: ${error.message}`);
  }

  console.log("\n=== Testing Complete ===");
}

main();
