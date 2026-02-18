"""Index creation with vector and metadata fields."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glide_sync import GlideClient, GlideClusterClient


def create_vector_index(
    client: "GlideClient | GlideClusterClient",
    index_name: str,
    vector_field: str = "embedding",
    dimensions: int = 1536,
    distance_metric: str = "COSINE",
    metadata_fields: dict[str, str] | None = None,
) -> None:
    """Create vector search index with metadata fields.

    Args:
        client: GLIDE client instance
        index_name: Name for the index
        vector_field: Name of vector field (default: "embedding")
        dimensions: Vector dimensions (default: 1536)
        distance_metric: "COSINE", "L2", or "IP" (default: "COSINE")
        metadata_fields: Dict of {field_name: field_type} where type is "tag" or "numeric"

    Raises:
        ImportError: If valkey-glide-sync not installed
    """
    try:
        from glide_sync import ft
        from glide_shared.commands.server_modules.ft_options.ft_create_options import (
            DistanceMetricType,
            VectorField,
            VectorFieldAttributesFlat,
            VectorAlgorithm,
            VectorType,
            TagField,
            NumericField,
            FtCreateOptions,
        )
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync. "
            "Install with: pip install valkey-glide-sync>=2.0.0"
        )

    # Map distance metric
    distance_map = {
        "COSINE": DistanceMetricType.COSINE,
        "L2": DistanceMetricType.L2,
        "IP": DistanceMetricType.IP,
    }

    # Build schema
    schema = [
        VectorField(
            vector_field,
            VectorAlgorithm.FLAT,
            VectorFieldAttributesFlat(
                dimensions=dimensions,
                distance_metric=distance_map[distance_metric],
                type=VectorType.FLOAT32,
            ),
        )
    ]

    # Add metadata fields
    if metadata_fields:
        for field_name, field_type in metadata_fields.items():
            if field_type == "tag":
                schema.append(TagField(field_name))
            elif field_type == "numeric":
                schema.append(NumericField(field_name))

    # Create index
    ft.create(
        client,
        index_name,
        schema,
        FtCreateOptions(prefixes=[f"{index_name}:"]),
    )


def index_exists(client: "GlideClient | GlideClusterClient", index_name: str) -> bool:
    """Check if index exists.

    Args:
        client: GLIDE client instance
        index_name: Name of index to check

    Returns:
        True if index exists, False otherwise
    """
    try:
        from glide_sync import ft
        from glide_shared.exceptions import RequestError
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync. "
            "Install with: pip install valkey-glide-sync>=2.0.0"
        )

    try:
        ft.info(client, index_name)
        return True
    except RequestError:
        return False


def drop_index(client: "GlideClient | GlideClusterClient", index_name: str) -> None:
    """Drop index if it exists.

    Args:
        client: GLIDE client instance
        index_name: Name of index to drop
    """
    try:
        from glide_sync import ft
        from glide_shared.exceptions import RequestError
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync. "
            "Install with: pip install valkey-glide-sync>=2.0.0"
        )

    try:
        ft.dropindex(client, index_name)
    except RequestError:
        pass  # Index didn't exist
