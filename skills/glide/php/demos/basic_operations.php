<?php

// Create ValkeyGlide client
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);

// Basic SET operation
$setResult = $client->set('hello', 'world');
echo "SET result: " . $setResult . "\n";

// Basic GET operation
$getValue = $client->get('hello');
echo "GET result: " . $getValue . "\n";

// PING operation
$pingResult = $client->ping();
echo "PING result: " . $pingResult . "\n";

// Error handling - try to use wrong type
try {
    $client->lpush('hello', 'item');
} catch (Exception $e) {
    echo "Expected error (WRONGTYPE): " . $e->getMessage() . "\n";
}

// Cleanup
$client->del(['hello']);

echo "Basic operations completed\n";

// Close the connection
$client->close();
