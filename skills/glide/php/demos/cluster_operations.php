<?php

// Create ValkeyGlideCluster client
$client = new ValkeyGlideCluster(addresses: [['host' => getenv('VALKEY_HOST') ?: 'localhost', 'port' => 7000]]);

echo "Connected to cluster\n";

// Atomic batch with same slot (using hash tags)
$client->multi();
$client->set('{user}:1:name', 'Alice');
$client->set('{user}:1:email', 'alice@example.com');
$client->get('{user}:1:name');
$results = $client->exec();
echo "Atomic batch (same slot): " . json_encode($results) . "\n";

// Try atomic batch with different slots (will fail)
try {
    $client->multi();
    $client->set('key1', 'value1');
    $client->set('key2', 'value2');
    $client->exec();
} catch (Exception $e) {
    echo "Expected CROSSSLOT error: " . $e->getMessage() . "\n";
}

// Non-atomic pipeline (can span multiple slots)
$pipeline = $client->pipeline();
$pipeline->set('key1', 'value1');
$pipeline->set('key2', 'value2');
$pipeline->get('key1');
$pipeline->get('key2');
$pipelineResults = $client->exec();
echo "Pipeline (multi-slot): " . json_encode($pipelineResults) . "\n";

// Cleanup with non-atomic pipeline
$pipeline = $client->pipeline();
$pipeline->del(['{user}:1:name', '{user}:1:email']);
$pipeline->del(['key1']);
$pipeline->del(['key2']);
$cleanupResults = $client->exec();
echo "Cleanup batch results: " . json_encode($cleanupResults) . "\n";

echo "Cluster operations completed\n";

// Close the connection
$client->close();
