#!/bin/bash
set -e

VALKEY_HOST=${VALKEY_HOST:-localhost}

echo "=== C# GLIDE Demo Validation ==="
echo "Using VALKEY_HOST: $VALKEY_HOST"
echo ""

demos=("BasicOperations" "BatchPipeline" "ClusterOperations")

for demo in "${demos[@]}"; do
    echo "--- Testing $demo ---"
    docker build -t csharp-glide-demo \
        --build-arg DEMO=$demo \
        -f Dockerfile \
        --quiet \
        . 2>&1 | grep -v "^#" || true
    
    docker run --rm \
        -e VALKEY_HOST=$VALKEY_HOST \
        --network host \
        -v $(pwd)/${demo}.cs:/app/Program.cs:ro \
        -v $(pwd)/${demo}.csproj:/app/demo.csproj:ro \
        csharp-glide-demo \
        2>&1 || echo "❌ $demo failed"
    
    echo ""
done

echo "=== Validation Complete ==="
