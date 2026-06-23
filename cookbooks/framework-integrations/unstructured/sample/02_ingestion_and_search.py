"""02 — Document Ingestion & Search: partition, embed, upload, then query."""

import asyncio
import os

import numpy as np
from sentence_transformers import SentenceTransformer
from unstructured.chunking.title import chunk_by_title
from unstructured.partition.auto import partition

from glide import FtSearchOptions, GlideClient, GlideClientConfiguration, NodeAddress, ft
from unstructured_ingest.data_types.file_data import FileData, SourceIdentifiers
from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig,
    ValkeyConnectionConfig,
    ValkeyUploader,
    ValkeyUploaderConfig,
)

VALKEY_HOST = os.getenv("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
SAMPLE_PDF = os.getenv("SAMPLE_PDF", "sample.pdf")
INDEX_NAME = "documents_index"
KEY_PREFIX = "doc:unstructured:"

model = SentenceTransformer("all-MiniLM-L6-v2")


def ingest():
    """Partition, chunk, embed, and upload a document."""
    print(f"Partitioning '{SAMPLE_PDF}'...")
    elements = partition(SAMPLE_PDF)
    print(f"  {len(elements)} elements")

    chunks = chunk_by_title(elements, max_characters=500)
    print(f"  {len(chunks)} chunks")

    print("Generating embeddings...")
    data = []
    for chunk in chunks:
        data.append({
            "element_id": chunk.id,
            "type": chunk.category,
            "text": chunk.text,
            "metadata": {
                "page_number": chunk.metadata.page_number or 0,
                "filename": chunk.metadata.filename or SAMPLE_PDF,
            },
            "embeddings": model.encode(chunk.text).tolist(),
        })

    print(f"Uploading {len(data)} chunks to Valkey...")
    uploader = ValkeyUploader(
        connection_config=ValkeyConnectionConfig(
            host=VALKEY_HOST, port=VALKEY_PORT, ssl=False,
            access_config=ValkeyAccessConfig(),
        ),
        upload_config=ValkeyUploaderConfig(
            batch_size=50, key_prefix=KEY_PREFIX, index_name=INDEX_NAME,
        ),
    )

    file_data = FileData(
        source_identifiers=SourceIdentifiers(fullpath=SAMPLE_PDF, filename=SAMPLE_PDF),
        connector_type="valkey", identifier=SAMPLE_PDF,
    )
    asyncio.run(uploader.run_data_async(data=data, file_data=file_data))
    print(f"Done — {len(data)} chunks stored.\n")


async def search(query_text: str, top_k: int = 3):
    """KNN search against the ingested documents."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    query_vec = model.encode(query_text)
    query_bytes = np.array(query_vec, dtype=np.float32).tobytes()

    ft_query = f"*=>[KNN {top_k} @embedding $vec]"
    options = FtSearchOptions(params={"vec": query_bytes})
    results = await ft.search(client, INDEX_NAME, ft_query, options)

    print(f"Query: '{query_text}' — {results[0]} hits")
    for entry in results[1:]:
        if not isinstance(entry, dict):
            continue
        for key, fields in entry.items():
            text = fields.get(b"text", b"").decode()
            score = 1.0 - float(fields.get(b"__embedding_score", b"1.0"))
            print(f"  [{score:.3f}] {text[:120]}...")
    print()

    await client.close()


def main():
    ingest()
    asyncio.run(search("What is the main topic?"))
    asyncio.run(search("key findings and results"))


if __name__ == "__main__":
    main()
