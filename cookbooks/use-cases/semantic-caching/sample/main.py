"""Semantic Caching with Valkey — Demo Script.

Demonstrates caching LLM responses by semantic similarity using
Valkey's vector search (FT.SEARCH KNN) and Ollama embeddings.

Requirements:
    - Valkey running on localhost:6379 with the search module
    - Ollama running with nomic-embed-text model pulled
"""

import hashlib
import time

import numpy as np
import ollama
import valkey

# --- Configuration ---
VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768
SIMILARITY_THRESHOLD = 0.15  # COSINE distance: 0=identical, 2=opposite
CACHE_TTL = 3600  # 1 hour
LLM_MODEL = "llama3.2:1b"

# --- Clients ---
client = valkey.Valkey(host=VALKEY_HOST, port=VALKEY_PORT)


def create_cache_index():
    """Create a vector index for the semantic cache."""
    try:
        client.execute_command(
            "FT.CREATE",
            "cache_idx",
            "ON",
            "HASH",
            "PREFIX",
            "1",
            "cache:",
            "SCHEMA",
            "prompt",
            "TAG",
            "response",
            "TAG",
            "embedding",
            "VECTOR",
            "HNSW",   # Algorithm: Hierarchical Navigable Small World
            "6",      # Number of config params that follow (3 key-value pairs)
            "TYPE",
            "FLOAT32",
            "DIM",
            str(EMBEDDING_DIM),
            "DISTANCE_METRIC",
            "COSINE",
        )
        print("Cache index created")
    except valkey.ResponseError as e:
        if "Index already exists" in str(e):
            print("Cache index already exists")
        else:
            raise


def get_embedding(text: str) -> bytes:
    """Embed text using Ollama and return as FLOAT32 bytes."""
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    vec = response["embeddings"][0]
    return np.array(vec, dtype=np.float32).tobytes()


def semantic_cache_lookup(prompt: str) -> dict:
    """Check if a semantically similar prompt is cached."""
    query_vec = get_embedding(prompt)

    results = client.execute_command(
        "FT.SEARCH",
        "cache_idx",
        "*=>[KNN 1 @embedding $query_vec AS score]",
        "PARAMS",
        "2",
        "query_vec",
        query_vec,
    )

    if results[0] > 0:
        fields = results[2]
        field_dict = {}
        for j in range(0, len(fields), 2):
            k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
            v = fields[j + 1]
            if isinstance(v, bytes):
                try:
                    v = v.decode()
                except UnicodeDecodeError:
                    pass
            field_dict[k] = v

        score = float(field_dict.get("score", "999"))
        if score < SIMILARITY_THRESHOLD:
            return {
                "hit": True,
                "response": field_dict.get("response", ""),
                "cached_prompt": field_dict.get("prompt", ""),
                "score": score,
            }

    return {"hit": False}


def cache_response(prompt: str, response: str):
    """Store a prompt+response in the cache."""
    embedding_bytes = get_embedding(prompt)
    cache_key = f"cache:{hashlib.md5(prompt.encode()).hexdigest()}"
    client.hset(
        cache_key,
        mapping={
            "prompt": prompt,
            "response": response,
            "embedding": embedding_bytes,
            "created_at": str(time.time()),
        },
    )
    client.expire(cache_key, CACHE_TTL)


def ask_with_cache(prompt: str) -> dict:
    """Check cache first, then call LLM if needed."""
    start = time.time()

    # 1. Check cache
    cache_result = semantic_cache_lookup(prompt)

    if cache_result["hit"]:
        elapsed = (time.time() - start) * 1000
        return {
            "response": cache_result["response"],
            "source": "cache",
            "similarity_score": cache_result["score"],
            "latency_ms": round(elapsed, 1),
        }

    # 2. Cache miss — call LLM
    llm_response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = llm_response["message"]["content"]

    # 3. Cache the response
    cache_response(prompt, answer)

    elapsed = (time.time() - start) * 1000
    return {
        "response": answer,
        "source": "llm",
        "latency_ms": round(elapsed, 1),
    }


def main():
    print("=== Semantic Cache Demo ===\n")

    print("Creating cache index...")
    create_cache_index()
    print()

    queries = [
        ("What is Valkey?", "First query — expect cache MISS"),
        ("Can you explain what Valkey is?", "Similar query — expect cache HIT"),
        ("How do I cook pasta?", "Different topic — expect cache MISS"),
    ]

    hits = 0
    misses = 0

    for prompt, description in queries:
        print(f'--- {description} ---')
        print(f'Query: "{prompt}"')
        result = ask_with_cache(prompt)
        print(f"Source: {result['source']}, Latency: {result['latency_ms']}ms")
        if result["source"] == "cache":
            print(f"Similarity score: {result['similarity_score']:.4f}")
            hits += 1
        else:
            misses += 1
        # Truncate response for readability
        response_preview = result["response"][:100]
        print(f"Response: {response_preview}...")
        print()

    total = hits + misses
    hit_rate = hits / total * 100 if total > 0 else 0
    print(f"Cache Stats: {misses} misses, {hits} hits ({hit_rate:.0f}% hit rate)")


if __name__ == "__main__":
    main()
