"""MetaGPT + Valkey RAG Vector Store — Full Lifecycle Demo.

Demonstrates the synchronous ValkeyVectorStore behavior documented in
FoundationAgents/MetaGPT#2063 (open, unmerged at the time of writing), using
this cookbook's standalone reimplementation (`valkey_vector_store.py`)
instead of importing MetaGPT:
1. Connecting to Valkey with the synchronous valkey-glide client (glide_sync)
2. Creating an FT.SEARCH index over JSON documents (HNSW)
3. Storing embedding nodes as JSON documents in atomic batches
4. Running KNN similarity search via FT.SEARCH
5. Deleting all chunks of a source document
6. Dropping the index and cleaning up keys

The integration uses the SYNCHRONOUS GLIDE client — there is no await/asyncio.

To keep the demo runnable without an API key, embeddings are produced by a tiny
deterministic local function. In a real MetaGPT app the embeddings come from your
configured embedding model (e.g. OpenAI text-embedding-3-small, 1536 dims).

Requirements:
    pip install -r requirements.txt

Environment variables:
    VALKEY_HOST   - Valkey server hostname (default: localhost)
    VALKEY_PORT   - Valkey server port (default: 6379)

    Copy .env.example to .env to override these; load_dotenv() picks it up.
"""

from __future__ import annotations

import hashlib
import os
import sys

# Load .env (if present) before reading env vars below, so a copied
# .env.example actually takes effect.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is optional; the sample still works with exported env vars.
    pass

# Guard the third-party imports so the most common new-user failure
# (dependencies not installed) prints the actionable hint below instead of an
# opaque module-level ModuleNotFoundError before main() ever runs.
try:
    from llama_index.core.schema import TextNode
    from llama_index.core.vector_stores.types import VectorStoreQuery

    from valkey_vector_store import ValkeyVectorStore
except ImportError as import_err:
    print(f"\nMissing dependency: {import_err}", file=sys.stderr)
    print("\nHints:", file=sys.stderr)
    print("  - Install the sample dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

# Small dimension keeps the demo fast and lets us hand-craft illustrative vectors.
# Real embedding models use far larger dims (e.g. 1536 for OpenAI text-embedding-3-small).
EMBED_DIM = 8

INDEX_NAME = "metagpt_cookbook_demo"
KEY_PREFIX = "metagpt:cookbook:demo:"


def embed(text: str) -> list[float]:
    """Deterministic local embedding so the demo runs without an API key.

    Hashes the text into EMBED_DIM float buckets. This is NOT semantically
    meaningful — it only gives stable, reproducible vectors for the demo.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i] / 255.0 for i in range(EMBED_DIM)]


def main() -> None:
    """Run the full vector store lifecycle demo."""
    print("=" * 60)
    print("MetaGPT + Valkey RAG Vector Store Demo")
    print("=" * 60)

    # This example connects without authentication for local development.
    # Always enable authentication and TLS for production deployments.
    store = ValkeyVectorStore(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        index_name=INDEX_NAME,
        prefix=KEY_PREFIX,
        vector_dimensions=EMBED_DIM,
        distance_metric="COSINE",   # COSINE, L2, or IP
        vector_algorithm="HNSW",    # HNSW (approximate) or FLAT (exact). FLAT is
                                    # the better pick for <1000 docs like this demo;
                                    # HNSW is shown here since it's the production default.
        request_timeout=5000,       # 5s — GLIDE defaults to 250ms, too low off-localhost
        client_name="metagpt_rag_client",
        # For production, enable auth and TLS (ValkeyVectorStore supports both):
        #   password=os.environ.get("VALKEY_PASSWORD"),
        #   use_tls=True,
    )

    print(f"\n-> Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")

    try:
        # Defensive cleanup: drop any stale index/keys from a prior failed run so
        # re-running the demo is idempotent (does not accumulate stale documents).
        # Safe on the very first run: drop_index() checks FT._LIST and no-ops the
        # FT.DROPINDEX when the index is absent, then SCANs for orphaned keys.
        store.drop_index()

        store.ensure_index()
        print(f"Created FT.SEARCH index '{INDEX_NAME}' (HNSW, {EMBED_DIM} dims)")

        # --- Step 1: Add documents ---
        print("\n-> Storing documents as JSON with vector embeddings...")
        documents = [
            "Valkey supports HNSW and FLAT vector indexes for similarity search.",
            "FT.SEARCH runs KNN queries to find the nearest embeddings.",
            "MetaGPT assigns roles to LLMs so they collaborate like a software company.",
            "The valkey-glide-sync package exposes a synchronous client as glide_sync.",
            "Bananas are an excellent source of potassium.",
        ]
        nodes = [
            TextNode(text=text, embedding=embed(text), id_=f"doc_{i}")
            for i, text in enumerate(documents)
        ]
        ids = store.add(nodes)
        print(f"Stored {len(ids)} documents: {ids}")

        # --- Step 2: KNN similarity search ---
        query_text = "How does Valkey index vectors for search?"
        print(f"\n-> Searching for: {query_text!r}")
        result = store.query(
            VectorStoreQuery(query_embedding=embed(query_text), similarity_top_k=3)
        )
        print(f"Top {len(result.nodes)} matches:")
        # The query text is closest to the Valkey/FT.SEARCH docs, so we expect hits.
        # A count of 0 usually means indexing lag or a dimension/index mismatch —
        # assert so the demo fails loudly instead of printing a misleading success.
        assert len(result.nodes) > 0, "KNN search returned no results — check index and embeddings"
        for rank, (node, score) in enumerate(zip(result.nodes, result.similarities), 1):
            print(f"   {rank}. [{score:.4f}] {node.text[:60]}...")

        # --- Step 3: Delete a source document ---
        print("\n-> Deleting document 'doc_4' (the banana fact)...")
        # delete() matches stored docs on ref_doc_id OR doc_id. These nodes set
        # only id_ (no ref_doc_id), and add() stores ref_doc_id = doc_id as a
        # fallback, so passing the node id "doc_4" removes the matching document.
        store.delete("doc_4")
        remaining = store.scan_all_docs()
        print(f"Deleted. {len(remaining)} documents remain in the store.")
        assert len(remaining) == 4, f"expected 4 documents after delete, found {len(remaining)}"

        print("\n" + "=" * 60)
        print("Demo complete!")
        print("=" * 60)

    finally:
        # --- Cleanup: drop the demo index and all its keys ---
        try:
            store.drop_index()
            print("\nCleaned up demo index and keys")
        except Exception as cleanup_err:  # noqa: BLE001 — best-effort cleanup
            print(f"Cleanup incomplete: {cleanup_err}", file=sys.stderr)
        store.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001 — surface a friendly hint at the top level
        print(f"\nError: {e}", file=sys.stderr)
        print("\nHints:", file=sys.stderr)
        print(
            "  - Ensure Valkey is running: "
            "docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0",
            file=sys.stderr,
        )
        print("  - Ensure dependencies are installed: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
