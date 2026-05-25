"""
CocoIndex + Valkey RAG Pipeline

Index (use `-L` for live mode, omit for one-shot catch-up):
    cocoindex update main
    cocoindex update -L main

Query the index:
    python main.py "your query"

Pipeline: walk markdown files -> chunk -> embed -> store in Valkey (HNSW index).
"""

from __future__ import annotations

import asyncio
import pathlib
import struct
import sys
from typing import AsyncIterator

from dotenv import load_dotenv
from glide import GlideClient
from glide.async_commands import ft
from glide.async_commands.ft import FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_search_options import ReturnField

import cocoindex as coco
from cocoindex.connectors import localfs, valkey
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike, PatternFilePathMatcher
from cocoindex.resources.id import IdGenerator


# Configuration
VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
INDEX_NAME = "rag_documents"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5

# Context keys — stable identities for the Valkey client and embedder
VALKEY_DB = coco.ContextKey[GlideClient]("rag_valkey")
EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder", detect_change=True)

_splitter = RecursiveSplitter()


# ============================================================================
# Lifespan — manages the Valkey connection and embedder
# ============================================================================


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)
    builder.provide(VALKEY_DB, client)
    builder.provide(EMBEDDER, SentenceTransformerEmbedder(EMBED_MODEL))
    yield
    await client.close()


# ============================================================================
# Pipeline functions
# ============================================================================


@coco.fn
async def process_chunk(
    chunk: Chunk,
    filename: pathlib.PurePath,
    id_gen: IdGenerator,
    target: valkey.IndexTarget,
) -> None:
    """Embed a single chunk and declare it in the Valkey index."""
    embedder = coco.use_context(EMBEDDER)
    embedding = await embedder.embed(chunk.text)

    doc_id = await id_gen.next_id(chunk.text)
    target.declare_document(valkey.Document(
        id=str(doc_id),
        vector=embedding.tolist(),
        payload={
            "filename": str(filename),
            "text": chunk.text,
            "chunk_start": str(chunk.start.char_offset),
            "chunk_end": str(chunk.end.char_offset),
        },
    ))


@coco.fn(memo=True)
async def process_file(
    file: FileLike,
    target: valkey.IndexTarget,
) -> None:
    """Split a file into chunks and process each one.

    memo=True means CocoIndex caches the result keyed by hash(file content).
    If the file hasn't changed, this function is skipped entirely.
    """
    text = await file.read_text()
    chunks = _splitter.split(
        text, chunk_size=2000, chunk_overlap=500, language="markdown"
    )
    id_gen = IdGenerator()
    await coco.map(process_chunk, chunks, file.file_path.path, id_gen, target)


@coco.fn
async def app_main(sourcedir: pathlib.Path) -> None:
    """Declare the pipeline: source -> transform -> target."""
    # Declare the Valkey index target
    target_index = await valkey.mount_index_target(
        VALKEY_DB,
        INDEX_NAME,
        await valkey.IndexSchema.create(
            vectors=valkey.VectorDef(schema=EMBEDDER, distance="cosine"),
        ),
    )

    # Declare the source: walk markdown files with live watching support
    files = localfs.walk_dir(
        sourcedir,
        recursive=True,
        path_matcher=PatternFilePathMatcher(included_patterns=["**/*.md"]),
        live=True,
    )

    # Connect source to target through the processing functions
    await coco.mount_each(process_file, files.items(), target_index)


# Register the app
app = coco.App(
    coco.AppConfig(name="ValkeyRAG"),
    app_main,
    sourcedir=pathlib.Path("./markdown_files"),
)


# ============================================================================
# Query demo — semantic search using Valkey FT.SEARCH
# ============================================================================


async def query_once(
    client: GlideClient,
    embedder: SentenceTransformerEmbedder,
    query_text: str,
    *,
    top_k: int = TOP_K,
) -> None:
    """Run a KNN vector search against the Valkey index."""
    query_vec = await embedder.embed(query_text)
    vec_blob = struct.pack(f"<{len(query_vec)}f", *query_vec.tolist())

    knn_query = f"*=>[KNN {top_k} @vector $query_vec AS score]"

    results = await ft.search(
        client,
        INDEX_NAME,
        knn_query,
        options=FtSearchOptions(
            params={"query_vec": vec_blob},
            return_fields=[
                ReturnField("text"),
                ReturnField("filename"),
                ReturnField("score"),
            ],
        ),
    )

    print(f"\nResults for: \"{query_text}\"\n{'=' * 60}")

    if not results or len(results) < 2:
        print("No results found.")
        return

    # FT.SEARCH returns [total_count, {key: {field: value}, ...}]
    total = results[0]
    print(f"Total matches: {total}\n")

    docs = results[1]  # dict of {key: {field: value}}
    for key, fields in docs.items():
        key_str = key.decode() if isinstance(key, bytes) else key
        score = fields.get(b"score", fields.get("score", b"?"))
        filename = fields.get(b"filename", fields.get("filename", b"<unknown>"))
        text = fields.get(b"text", fields.get("text", b""))

        # Decode bytes
        if isinstance(score, bytes):
            score = score.decode()
        if isinstance(filename, bytes):
            filename = filename.decode()
        if isinstance(text, bytes):
            text = text.decode()

        print(f"[score: {score}] {filename}")
        print(f"    {text[:120]}...")
        print("---")


async def query(initial_query: str | None = None) -> None:
    """Interactive or one-shot query mode."""
    embedder = SentenceTransformerEmbedder(EMBED_MODEL)
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)

    try:
        if initial_query is not None:
            await query_once(client, embedder, initial_query)
            return

        while True:
            q = input("\nEnter search query (or Enter to quit): ").strip()
            if not q:
                break
            await query_once(client, embedder, q)
    finally:
        await client.close()


if __name__ == "__main__":
    load_dotenv()
    initial = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    asyncio.run(query(initial))
