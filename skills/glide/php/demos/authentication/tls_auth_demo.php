<?php
/**
 * PHP GLIDE TLS + Authentication Test
 * 
 * Tests TLS connectivity with password authentication on port 6479.
 * 
 * Usage:
 *   export VALKEY_HOST=localhost
 *   cd php
 *   docker run --rm -v $(pwd)/demos:/app -e VALKEY_HOST=${VALKEY_HOST} --network host php-glide php /app/authentication/tls_auth_demo.php
 */

echo "PHP GLIDE TLS + Authentication Testing\n\n";
echo "=== Testing TLS + Authentication (Port 6479) ===\n";

$host = getenv('VALKEY_HOST') ?: 'localhost';

// For self-signed certificates (testing only)
// ⚠️ WARNING: use_insecure_tls disables certificate verification
// In production, use proper CA-signed certificates
$client = new ValkeyGlide();

try {
    $client->connect(
        addresses: [['host' => $host, 'port' => 6479]],
        use_tls: true,
        credentials: ['password' => 'mypassword'],
        request_timeout: 5000
    );
    
    // Test operations
    $client->set('tls_test_php', 'Hello with TLS!');
    $value = $client->get('tls_test_php');
    echo "✓ TLS works: $value\n";
    
    // Cleanup
    $client->del(['tls_test_php']);
    
    $client->close();
    
    echo "\n=== Testing Complete ===\n";
} catch (Exception $e) {
    echo "⚠ TLS test failed: " . $e->getMessage() . "\n";
    echo "  Note: PHP GLIDE v1.0.0 may not support insecure TLS mode\n";
    echo "  Use proper CA-signed certificates in production\n";
    exit(1);
}
