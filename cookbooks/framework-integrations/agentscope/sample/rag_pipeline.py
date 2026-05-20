# -*- coding: utf-8 -*-
"""Cookbook 02 - RAG Pipeline with AgentScope + Valkey.

Demonstrates: chunking text, generating embeddings with Amazon Bedrock
Titan, storing in Valkey, and retrieving relevant context for a query.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    pip install agentscope[valkey] boto3
    AWS credentials configured (via env vars, ~/.aws/credentials, or IAM role)
"""

from __future__ import annotations

import asyncio
import json

import boto3

from agentscope.message import TextBlock
from agentscope.rag import Document, DocMetadata, ValkeyStore

# --- Configuration ---

BEDROCK_MODEL_ID = "amazon.titan-embed-text-v2:0"
BEDROCK_REGION = "us-east-1"
CHUNK_SIZE = 200
CHUNK_OVERLAP = 30

# --- Sample knowledge base ---

SOURCE_TEXT = """\
Valkey is an open-source, high-performance key-value datastore that supports \
strings, hashes, lists, sets, sorted sets, streams, and more. The Search module \
adds full-text search and vector similarity search with HNSW and FLAT indexing \
algorithms. Vector search enables semantic queries over embeddings stored \
directly in Valkey, making it ideal for RAG pipelines, recommendation systems, \
and similarity matching. Valkey is wire-compatible with Redis OSS and can serve \
as a drop-in replacement. The valkey-glide client library provides async access \
from Python, Java, Node.js, and Go with built-in connection pooling and cluster \
support.\
"""


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Amazon Bedrock Titan."""
    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    embeddings = []
    for text in texts:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        embeddings.append(result["embedding"])
    return embeddings


async def main() -> None:
    """Run the RAG pipeline example."""
    print("=== AgentScope + Valkey RAG Pipeline ===\n")

    # 1. Chunk the source text
    chunks = chunk_text(SOURCE_TEXT, CHUNK_SIZE, CHUNK_OVERLAP)
    print(f"Created {len(chunks)} chunks from source text")

    # 2. Generate embeddings
    embeddings = embed(chunks)
    dimensions = len(embeddings[0])
    print(f"Generated embeddings ({dimensions} dimensions)\n")

    # 3. Store in Valkey
    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="rag_demo_idx",
        prefix="rag:doc:",
        dimensions=dimensions,
        distance="COSINE",
    )

    documents = [
        Document(
            embedding=emb,
            metadata=DocMetadata(
                content=TextBlock(type="text", text=chunk),
                doc_id="valkey-overview",
                chunk_id=i,
                total_chunks=len(chunks),
            ),
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]

    await store.add(documents)
    print(f"Stored {len(documents)} chunks in Valkey")

    # Wait for indexing
    await asyncio.sleep(0.5)

    # 4. Query and retrieve
    queries = [
        "What indexing algorithms does Valkey support?",
        "Which programming languages have client libraries?",
        "Is Valkey compatible with Redis?",
    ]

    for query in queries:
        print(f"\nQuery: \"{query}\"")
        query_embedding = embed([query])[0]

        results = await store.search(
            query_embedding=query_embedding,
            limit=2,
            score_threshold=0.3,
        )

        for i, doc in enumerate(results, 1):
            text = doc.metadata.content["text"]
            preview = text[:80] + "..." if len(text) > 80 else text
            print(f"  [{i}] score={doc.score:.4f}: {preview}")

    # 5. Cleanup
    await store.drop_index()
    await store.close()
    print("\n\nDone! Cleaned up and closed connection.")


if __name__ == "__main__":
    asyncio.run(main())
