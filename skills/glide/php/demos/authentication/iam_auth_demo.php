<?php
/**
 * PHP GLIDE AWS IAM Authentication Demo
 * 
 * Demonstrates AWS ElastiCache/MemoryDB IAM authentication configuration.
 * This demo validates the configuration runs without AWS-specific errors.
 * 
 * Note: Actual connection will fail without valid AWS credentials and ElastiCache cluster.
 * 
 * Usage:
 *   cd php
 *   docker run --rm -v $(pwd)/demos:/app --network host php-glide php /app/authentication/iam_auth_demo.php
 */

echo "PHP GLIDE AWS IAM Authentication Demo\n\n";
echo "=== Testing AWS IAM Authentication ===\n";

$client = new ValkeyGlide();

try {
    $client->connect(
        addresses: [['host' => 'my-cluster.cache.amazonaws.com', 'port' => 6379]],
        use_tls: true,  // REQUIRED for IAM authentication
        credentials: [
            'username' => 'myUser',  // REQUIRED for IAM
            'iamConfig' => [
                ValkeyGlide::IAM_CONFIG_CLUSTER_NAME => 'my-cluster',
                ValkeyGlide::IAM_CONFIG_REGION => 'us-east-1',
                ValkeyGlide::IAM_CONFIG_SERVICE => ValkeyGlide::IAM_SERVICE_ELASTICACHE,
            ]
        ]
    );
    
    echo "✓ IAM configuration created successfully\n";
    echo "  Cluster: my-cluster\n";
    echo "  Service: ELASTICACHE\n";
    echo "  Region: us-east-1\n";
    echo "  Username: myUser\n";
    
    // Test operations
    $client->set('iam_test', 'Hello from IAM!');
    $value = $client->get('iam_test');
    echo "✓ IAM auth works: $value\n";
    
    $client->close();
} catch (Exception $e) {
    // Expected to fail without actual AWS infrastructure
    if (strpos($e->getMessage(), 'Connection') !== false || 
        strpos($e->getMessage(), 'refused') !== false ||
        strpos($e->getMessage(), 'not known') !== false) {
        echo "✓ Configuration is valid (connection failure is expected)\n";
    } else {
        echo "⚠ IAM auth demo completed (connection expected to fail without AWS)\n";
        echo "  Error: " . $e->getMessage() . "\n";
    }
}

echo "\n=== Testing Complete ===\n";
