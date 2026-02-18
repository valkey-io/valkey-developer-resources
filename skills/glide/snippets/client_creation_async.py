"""Async client creation with automatic cluster detection."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glide import GlideClient, GlideClusterClient


async def get_client(valkey_url: str) -> "GlideClient | GlideClusterClient":
    """Create async GLIDE client with automatic cluster detection.

    Args:
        valkey_url: Connection URL (e.g., "valkey://localhost:6379")

    Returns:
        GlideClusterClient if cluster mode, else GlideClient

    Raises:
        ImportError: If valkey-glide-async not installed
    """
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
            "Could not import valkey-glide-async. "
            "Install with: pip install valkey-glide-async>=2.0.0"
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
    """Parse Valkey URL to extract host and port.

    Supported formats:
    - valkey://localhost:6379
    - valkeyss://host:6379 (SSL)
    - valkey://user:pass@host:6379
    - valkey://host:6379/0 (with database)
    """
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
