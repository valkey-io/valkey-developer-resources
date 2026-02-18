"""Minimal aiohttp app demonstrating Valkey GLIDE async client patterns."""

import struct
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from glide import GlideClient, GlideClusterClient

client = None


async def get_client(valkey_url: str) -> "GlideClient | GlideClusterClient":
    """Create async GLIDE client with automatic cluster detection."""
    try:
        from glide import (
            GlideClient,
            GlideClientConfiguration,
            GlideClusterClient,
            GlideClusterClientConfiguration,
            NodeAddress,
        )
        from glide_shared.exceptions import ConnectionError, ClosingError, TimeoutError
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide. "
            "Install with: pip install valkey-glide>=2.0.0"
        )

    host, port = _parse_valkey_url(valkey_url)
    addresses = [NodeAddress(host, port)]

    # Try standalone first (more common for local dev)
    try:
        config = GlideClientConfiguration(addresses=addresses, request_timeout=5000)
        return await GlideClient.create(config)
    except (ConnectionError, ClosingError, TimeoutError) as e:
        # If standalone fails, try cluster
        try:
            config = GlideClusterClientConfiguration(addresses=addresses, request_timeout=5000)
            return await GlideClusterClient.create(config)
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


async def ensure_index(index_name: str, dimensions: int = 1536):
    """Create vector search index if it doesn't exist."""
    try:
        from glide import ft
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
            "Could not import valkey-glide. "
            "Install with: pip install valkey-glide>=2.0.0"
        )

    try:
        await ft.info(client, index_name)
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

    await ft.create(client, index_name, schema, FtCreateOptions(prefixes=["doc:"]))
    return {"status": "created"}


async def health(request):
    """Health check endpoint."""
    return web.json_response({"status": "ok"})


async def create_index(request):
    """Create vector search index."""
    data = await request.json()
    index_name = data.get("index_name", "docs_idx")
    dimensions = data.get("dimensions", 1536)

    result = await ensure_index(index_name, dimensions)
    return web.json_response(result)


async def delete_index(request):
    """Delete vector search index."""
    try:
        from glide import ft
        from glide_shared.exceptions import RequestError
    except ImportError:
        return web.json_response({"error": "valkey-glide not installed"}, status=500)

    index_name = request.match_info["index_name"]

    try:
        await ft.dropindex(client, index_name)
        return web.json_response({"status": "deleted", "index": index_name})
    except RequestError as e:
        return web.json_response({"error": f"Index not found: {e}"}, status=404)


async def recreate_index(request):
    """Delete and recreate vector search index."""
    try:
        from glide import ft
        from glide_shared.exceptions import RequestError
    except ImportError:
        return web.json_response({"error": "valkey-glide not installed"}, status=500)

    index_name = request.match_info["index_name"]
    data = await request.json() if request.can_read_body else {}
    dimensions = data.get("dimensions", 1536)

    # Delete if exists (check first to avoid error logs)
    try:
        await ft.info(client, index_name)
        await ft.dropindex(client, index_name)
    except RequestError:
        pass  # Index didn't exist

    # Recreate
    result = await ensure_index(index_name, dimensions)
    return web.json_response({"status": "recreated", "index": index_name, **result})


async def index_info(request):
    """Get index information."""
    try:
        from glide import ft
    except ImportError:
        return web.json_response({"error": "valkey-glide not installed"}, status=500)

    index_name = request.match_info["index_name"]

    try:
        info = await ft.info(client, index_name)
        return web.json_response({"index": index_name, "info": str(info)})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=404)


async def search(request):
    """Vector similarity search."""
    try:
        from glide import ft
        from glide_shared.commands.server_modules.ft_options.ft_search_options import (
            FtSearchOptions,
        )
    except ImportError:
        return web.json_response({"error": "valkey-glide not installed"}, status=500)

    data = await request.json()
    index_name = data.get("index_name", "docs_idx")
    vector = data.get("vector")
    k = data.get("k", 5)
    filter_expr = data.get("filter")

    if not vector:
        return web.json_response({"error": "vector required"}, status=400)

    # Build KNN query
    if filter_expr:
        query = f"({filter_expr})=>[KNN {k} @embedding $vector AS score]"
    else:
        query = f"*=>[KNN {k} @embedding $vector AS score]"

    # Convert to bytes
    embedding_buffer = struct.pack(f"{len(vector)}f", *vector)

    try:
        results = await ft.search(
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
                str_key = key.decode() if isinstance(key, bytes) else key
                str_fields = {}
                for field_key, field_value in fields.items():
                    str_field_key = field_key.decode() if isinstance(field_key, bytes) else field_key
                    # Skip binary fields (like embeddings)
                    if str_field_key == "embedding":
                        continue
                    try:
                        str_field_value = field_value.decode() if isinstance(field_value, bytes) else field_value
                        str_fields[str_field_key] = str_field_value
                    except (UnicodeDecodeError, AttributeError):
                        pass  # Skip binary fields
                docs[str_key] = str_fields

        return web.json_response({"count": count, "results": docs})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def add_document(request):
    """Add document with vector embedding."""
    data = await request.json()
    doc_id = data.get("id")
    embedding = data.get("embedding")
    category = data.get("category", "general")

    if not doc_id or not embedding:
        return web.json_response({"error": "id and embedding required"}, status=400)

    embedding_buffer = struct.pack(f"{len(embedding)}f", *embedding)

    key = f"doc:{doc_id}"
    await client.hset(key, {"embedding": embedding_buffer, "category": category})

    return web.json_response({"status": "added", "key": key})


async def init_app():
    """Initialize the application."""
    import os

    global client
    valkey_url = os.getenv("VALKEY_URL", "valkey://localhost:6379")
    client = await get_client(valkey_url)
    print(f"Connected to Valkey at {valkey_url}")

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/index/create", create_index)
    app.router.add_delete("/index/{index_name}", delete_index)
    app.router.add_put("/index/{index_name}", recreate_index)
    app.router.add_get("/index/info/{index_name}", index_info)
    app.router.add_post("/search", search)
    app.router.add_post("/document", add_document)

    return app


if __name__ == "__main__":
    import asyncio

    async def main():
        app = await init_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 5001)
        await site.start()
        print("Server running on http://localhost:5001")
        print("Press Ctrl+C to stop")
        await asyncio.Event().wait()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
