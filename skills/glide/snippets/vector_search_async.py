"""Async vector similarity search with KNN."""

import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glide import GlideClient, GlideClusterClient


async def vector_search(
    client: "GlideClient | GlideClusterClient",
    index_name: str,
    query_vector: list[float],
    k: int = 5,
    vector_field: str = "embedding",
    filter_expr: str | None = None,
) -> list[dict[str, Any]]:
    """Perform async vector similarity search.
    
    Args:
        client: Async GLIDE client instance
        index_name: Name of the index to search
        query_vector: Query embedding vector
        k: Number of results to return (default: 5)
        vector_field: Name of vector field (default: "embedding")
        filter_expr: Optional metadata filter (e.g., "@category:{tech}")
        
    Returns:
        List of matching documents with scores
        
    Raises:
        ImportError: If valkey-glide-async not installed
        
    Example:
        results = await vector_search(
            client,
            "docs_idx",
            [0.1, 0.2, 0.3],
            k=10,
            filter_expr="@category:{tech}"
        )
    """
    try:
        from glide import ft
        from glide_shared.commands.server_modules.ft_options.ft_search_options import (
            FtSearchOptions,
        )
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-async. "
            "Install with: pip install valkey-glide-async>=2.0.0"
        )

    # Build KNN query
    if filter_expr:
        query = f"({filter_expr})=>[KNN {k} @{vector_field} $vector AS score]"
    else:
        query = f"*=>[KNN {k} @{vector_field} $vector AS score]"

    # Convert vector to bytes
    embedding_buffer = struct.pack(f"{len(query_vector)}f", *query_vector)

    # Execute search
    results = await ft.search(
        client=client,
        index_name=index_name,
        query=query,
        options=FtSearchOptions(params={"vector": embedding_buffer}),
    )

    # Parse results: [count, {key: {field: value}}]
    count = results[0]
    docs = []
    if count > 0 and len(results) > 1:
        for key, fields in results[1].items():
            # Decode bytes to strings
            str_key = key.decode() if isinstance(key, bytes) else key
            str_fields = {}
            for field_key, field_value in fields.items():
                str_field_key = field_key.decode() if isinstance(field_key, bytes) else field_key
                # Skip binary fields (like embeddings) or try to decode
                if str_field_key == vector_field:
                    continue  # Skip vector field
                try:
                    str_field_value = field_value.decode() if isinstance(field_value, bytes) else field_value
                    str_fields[str_field_key] = str_field_value
                except (UnicodeDecodeError, AttributeError):
                    pass  # Skip binary fields
            
            doc = {"key": str_key, **str_fields}
            docs.append(doc)

    return docs


async def add_document(
    client: "GlideClient | GlideClusterClient",
    key: str,
    embedding: list[float],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Add document with vector embedding (async).
    
    Args:
        client: Async GLIDE client instance
        key: Document key (e.g., "doc:123")
        embedding: Document embedding vector
        metadata: Optional metadata fields
        
    Example:
        await add_document(
            client,
            "doc:1",
            [0.1, 0.2, 0.3],
            {"category": "tech", "year": 2024}
        )
    """
    # Convert vector to bytes
    embedding_buffer = struct.pack(f"{len(embedding)}f", *embedding)

    # Build field dict
    fields = {"embedding": embedding_buffer}
    if metadata:
        fields.update(metadata)

    # Store document
    await client.hset(key, fields)
