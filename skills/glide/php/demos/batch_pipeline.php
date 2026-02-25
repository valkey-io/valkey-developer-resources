<?php

// Create ValkeyGlide client
$client = new ValkeyGlide();
$client->connect(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 6379]]);

// Non-atomic pipeline
$pipeline = $client->pipeline();
$pipeline->set('user:1', 'Alice');
$pipeline->set('user:2', 'Bob');
$pipeline->get('user:1');
$pipeline->get('user:2');
$results = $client->exec();
echo "Pipeline results: " . json_encode($results) . "\n";

// Atomic transaction
$client->multi();
$client->set('counter', '0');
$client->incr('counter');
$client->incr('counter');
$client->get('counter');
$txResults = $client->exec();
echo "Transaction results: " . json_encode($txResults) . "\n";

// Cleanup
$client->del(['user:1', 'user:2', 'counter']);

echo "Batch/pipeline operations completed\n";

// Close the connection
$client->close();
