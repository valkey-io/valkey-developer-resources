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

# Build schema
schema = [
    VectorField(
        "content_vector",
        VectorAlgorithm.FLAT,  # or VectorAlgorithm.HNSW
        VectorFieldAttributesFlat(
            dimensions=1536,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        ),
    ),
    TagField("category"),
    NumericField("year"),
]

# Create index
ft.create(
    client,
    index_name,
    schema,
    FtCreateOptions(prefixes=["doc:"]),
)
