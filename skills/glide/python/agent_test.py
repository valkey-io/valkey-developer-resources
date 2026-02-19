#!/usr/bin/env python3
"""
Minimal Valkey GLIDE Demo App
Demonstrates core patterns from the GLIDE skill guide.
"""

from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DistanceMetricType,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    VectorType,
    TagField,
    FtCreateOptions,
)
from glide_shared.exceptions import RequestError


def create_client(host: str = "localhost", port: int = 6379) -> GlideClient:
    """Create GLIDE client with proper configuration."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        request_timeout=5000,
    )
    return GlideClient.create(config)


def create_index(client: GlideClient, index_name: str, dimensions: int = 3):
    """Create vector search index."""
    schema = [
        VectorField(
            "embedding",
            VectorAlgorithm.FLAT,
            VectorFieldAttributesFlat(
                dimensions=dimensions,
                distance_metric=DistanceMetricType.COSINE,
                type=VectorType.FLOAT32,
            ),
        ),
        TagField("category"),
    ]

    ft.create(client, index_name, schema, FtCreateOptions(prefixes=["doc:"]))


def add_documents(client: GlideClient):
    """Add sample documents with embeddings."""
    docs = [
        {"id": "doc:1", "text": "AI research", "category": "tech", "embedding": [0.1, 0.2, 0.3]},
        {"id": "doc:2", "text": "Cloud computing", "category": "tech", "embedding": [0.2, 0.3, 0.4]},
        {"id": "doc:3", "text": "Cooking recipes", "category": "food", "embedding": [0.9, 0.1, 0.2]},
    ]

    for doc in docs:
        import struct
        embedding_bytes = struct.pack(f"{len(doc['embedding'])}f", *doc["embedding"])
        client.hset(doc["id"], {
            "text": doc["text"],
            "category": doc["category"],
            "embedding": embedding_bytes,
        })


def search_vectors(client: GlideClient, index_name: str, query_vector: list[float], k: int = 2):
    """Perform vector similarity search."""
    import struct
    embedding_buffer = struct.pack(f"{len(query_vector)}f", *query_vector)

    query = f"*=>[KNN {k} @embedding $vector AS score]"
    results = ft.search(
        client=client,
        index_name=index_name,
        query=query,
        options=FtSearchOptions(params={"vector": embedding_buffer}),
    )

    # Results format: [count, {key: {field: value}}]
    count = results[0]
    doc_dict = results[1]
    
    docs = []
    for key, fields in doc_dict.items():
        doc_key = key.decode() if isinstance(key, bytes) else key
        doc = {"id": doc_key}
        for field, value in fields.items():
            field_name = field.decode() if isinstance(field, bytes) else field
            if field_name != "embedding":  # Skip binary field
                doc[field_name] = value.decode() if isinstance(value, bytes) else value
        docs.append(doc)

    return docs


def main():
    """Run demo."""
    index_name = "demo_idx"

    # Create client
    print("Connecting to Valkey...")
    client = create_client("aux.obsidian.home")

    # Drop existing index
    try:
        ft.dropindex(client, index_name)
        print(f"Dropped existing index: {index_name}")
    except RequestError:
        pass

    # Create index
    print(f"Creating index: {index_name}")
    create_index(client, index_name)

    # Add documents
    print("Adding documents...")
    add_documents(client)

    # Search
    print("\nSearching for tech-related content...")
    query_vector = [0.15, 0.25, 0.35]
    results = search_vectors(client, index_name, query_vector, k=2)

    print(f"Found {len(results)} results:")
    for doc in results:
        print(f"  - {doc['id']}: {doc.get('text')} (category: {doc.get('category')})")

    # Cleanup
    client.close()
    print("\nDemo complete!")


if __name__ == "__main__":
    main()
