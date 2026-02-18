#!/bin/bash
# Test all endpoints from README.md

set -e

BASE_URL="http://localhost:5001"

echo "Testing Aiohttp Demo Endpoints"
echo "================================"

echo -e "\n1. Health Check"
curl -s $BASE_URL/health | jq .

echo -e "\n2. Create Index"
curl -s -X POST $BASE_URL/index/create \
  -H "Content-Type: application/json" \
  -d '{"index_name": "docs_idx", "dimensions": 3}' | jq .

echo -e "\n3. Add Document 1"
curl -s -X POST $BASE_URL/document \
  -H "Content-Type: application/json" \
  -d '{"id": "doc1", "embedding": [0.1, 0.2, 0.3], "category": "tech"}' | jq .

echo -e "\n4. Add Document 2"
curl -s -X POST $BASE_URL/document \
  -H "Content-Type: application/json" \
  -d '{"id": "doc2", "embedding": [0.2, 0.3, 0.4], "category": "science"}' | jq .

echo -e "\n5. Add Document 3"
curl -s -X POST $BASE_URL/document \
  -H "Content-Type: application/json" \
  -d '{"id": "doc3", "embedding": [0.1, 0.3, 0.5], "category": "tech"}' | jq .

echo -e "\nWaiting for indexing..."
sleep 2

echo -e "\n6. Search (all)"
curl -s -X POST $BASE_URL/search \
  -H "Content-Type: application/json" \
  -d '{"index_name": "docs_idx", "vector": [0.1, 0.2, 0.3], "k": 5}' | jq .

echo -e "\n7. Search with Filter (tech only)"
curl -s -X POST $BASE_URL/search \
  -H "Content-Type: application/json" \
  -d '{"index_name": "docs_idx", "vector": [0.1, 0.2, 0.3], "k": 5, "filter": "@category:{tech}"}' | jq .

echo -e "\n8. Get Index Info"
curl -s $BASE_URL/index/info/docs_idx | jq .

echo -e "\n9. Recreate Index (nuke and rebuild)"
curl -s -X PUT $BASE_URL/index/docs_idx \
  -H "Content-Type: application/json" \
  -d '{"dimensions": 3}' | jq .

echo -e "\n10. Delete Index"
curl -s -X DELETE $BASE_URL/index/docs_idx | jq .

echo -e "\n================================"
echo "All endpoint tests completed!"
