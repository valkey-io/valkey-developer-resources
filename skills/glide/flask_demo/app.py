"""Minimal Flask app demonstrating Valkey GLIDE sync client patterns."""

from flask import Flask, jsonify, request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glide_sync import GlideClient, GlideClusterClient

app = Flask(__name__)
client = None


def get_client(valkey_url: str) -> "GlideClient | GlideClusterClient":
    """Create GLIDE client with automatic cluster detection."""
    try:
        from glide_sync import (
            GlideClient,
            GlideClientConfiguration,
            GlideClusterClient,
            GlideClusterClientConfiguration,
            NodeAddress,
        )
        from glide_shared.exceptions import ConnectionError, ClosingError, TimeoutError
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync. "
            "Install with: pip install valkey-glide-sync>=2.0.0"
        )

    host, port = _parse_valkey_url(valkey_url)
    addresses = [NodeAddress(host, port)]

    # Try standalone first (more common for local dev)
    try:
        config = GlideClientConfiguration(addresses=addresses, request_timeout=5000)
        return GlideClient.create(config)
    except (ConnectionError, ClosingError, TimeoutError) as e:
        # If standalone fails, try cluster
        try:
            config = GlideClusterClientConfiguration(addresses=addresses, request_timeout=5000)
            return GlideClusterClient.create(config)
        except (ConnectionError, ClosingError, TimeoutError) as cluster_error:
            raise RuntimeError(
                f"Failed to connect to Valkey at {valkey_url}. "
                f"Standalone error: {e}. Cluster error: {cluster_error}. "
                "Make sure Valkey is running."
            )


def _parse_valkey_url(url: str) -> tuple[str, int]:
    """Parse Valkey URL to extract host and port."""
    if "://" in url:
        url = url.split("://", 1)[1]
    if "@" in url:
        url = url.split("@", 1)[1]
    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        port_str = port_str.split("/")[0]
        port = int(port_str)
    else:
        host = url
        port = 6379
    return host, port


def ensure_index(index_name: str, dimensions: int = 1536):
    """Create vector search index if it doesn't exist."""
    try:
        from glide_sync import ft
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
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync. "
            "Install with: pip install valkey-glide-sync>=2.0.0"
        )

    try:
        ft.info(client, index_name)
        return {"status": "exists"}
    except RequestError:
        # Index doesn't exist, create it
        pass

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
    return {"status": "created"}


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route("/index/create", methods=["POST"])
def create_index():
    """Create vector search index."""
    data = request.json
    index_name = data.get("index_name", "docs_idx")
    dimensions = data.get("dimensions", 1536)

    result = ensure_index(index_name, dimensions)
    return jsonify(result)


@app.route("/index/info/<index_name>")
def index_info(index_name: str):
    """Get index information."""
    try:
        from glide_sync import ft
    except ImportError:
        return jsonify({"error": "valkey-glide-sync not installed"}), 500

    try:
        info = ft.info(client, index_name)
        return jsonify({"index": index_name, "info": str(info)})
    except (KeyError, ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 404


@app.route("/search", methods=["POST"])
def search():
    """Vector similarity search."""
    try:
        from glide_sync import ft
        from glide_shared.commands.server_modules.ft_options.ft_search_options import (
            FtSearchOptions,
        )
    except ImportError:
        return jsonify({"error": "valkey-glide-sync not installed"}), 500

    data = request.json
    index_name = data.get("index_name", "docs_idx")
    vector = data.get("vector")
    k = data.get("k", 5)
    filter_expr = data.get("filter")

    if not vector:
        return jsonify({"error": "vector required"}), 400

    # Build KNN query
    if filter_expr:
        query = f"({filter_expr})=>[KNN {k} @embedding $vector AS score]"
    else:
        query = f"*=>[KNN {k} @embedding $vector AS score]"

    # Convert to bytes
    import struct

    embedding_buffer = struct.pack(f"{len(vector)}f", *vector)

    try:
        results = ft.search(
            client=client,
            index_name=index_name,
            query=query,
            options=FtSearchOptions(params={"vector": embedding_buffer}),
        )
        
        # Decode bytes to strings for JSON serialization
        count = results[0]
        docs = {}
        if count > 0 and len(results) > 1:
            for key, fields in results[1].items():
                # Decode key
                str_key = key.decode() if isinstance(key, bytes) else key
                # Decode field values
                str_fields = {}
                for field_key, field_value in fields.items():
                    str_field_key = field_key.decode() if isinstance(field_key, bytes) else field_key
                    # Skip binary fields (like embeddings)
                    if str_field_key == "embedding":
                        continue
                    # Try to decode, skip if it fails (binary data)
                    try:
                        str_field_value = field_value.decode() if isinstance(field_value, bytes) else field_value
                        str_fields[str_field_key] = str_field_value
                    except (UnicodeDecodeError, AttributeError):
                        pass  # Skip binary fields
                docs[str_key] = str_fields
        
        return jsonify({"count": count, "results": docs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/document", methods=["POST"])
def add_document():
    """Add document with vector embedding."""
    data = request.json
    doc_id = data.get("id")
    embedding = data.get("embedding")
    category = data.get("category", "general")

    if not doc_id or not embedding:
        return jsonify({"error": "id and embedding required"}), 400

    import struct

    embedding_buffer = struct.pack(f"{len(embedding)}f", *embedding)

    key = f"doc:{doc_id}"
    client.hset(key, {"embedding": embedding_buffer, "category": category})

    return jsonify({"status": "added", "key": key})


if __name__ == "__main__":
    import os

    valkey_url = os.getenv("VALKEY_URL", "valkey://localhost:6379")
    client = get_client(valkey_url)
    print(f"Connected to Valkey at {valkey_url}")

    app.run(debug=True, port=5000)
