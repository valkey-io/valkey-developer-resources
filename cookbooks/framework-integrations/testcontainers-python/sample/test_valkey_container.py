"""CI tests for TestContainers Python + Valkey cookbook.

Uses ValkeyContainer to spin up ephemeral Valkey instances.
Requires Docker running on the host. No external Valkey server needed.
"""

from __future__ import annotations

import struct
import time
import uuid

import pytest
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ServerCredentials

from testcontainers.community.valkey import ValkeyContainer


@pytest.fixture(scope="module")
def valkey():
    """Start a Valkey bundle container for the test module."""
    with ValkeyContainer().with_bundle().with_image_tag("9.1.0") as container:
        yield container


@pytest.fixture(scope="module")
def client(valkey):
    """Create a GLIDE client connected to the test container."""
    config = GlideClientConfiguration(
        [NodeAddress(valkey.get_host(), valkey.get_exposed_port())]
    )
    c = GlideClient.create(config)
    yield c
    c.close()


class TestBasicOperations:
    """Test basic Valkey operations through TestContainers."""

    def test_ping(self, client: GlideClient):
        """Container responds to PING."""
        assert client.ping() == b"PONG"

    def test_set_and_get(self, client: GlideClient):
        """SET and GET round-trip works."""
        key = f"test:basic:{uuid.uuid4().hex[:8]}"
        client.set(key, "hello")
        assert client.get(key) == b"hello"

    def test_increment(self, client: GlideClient):
        """INCR atomically increments a counter."""
        key = f"test:counter:{uuid.uuid4().hex[:8]}"
        client.set(key, "0")
        client.incr(key)
        client.incr(key)
        assert client.get(key) == b"2"

    def test_expiration(self, client: GlideClient):
        """Keys expire after TTL."""
        key = f"test:ttl:{uuid.uuid4().hex[:8]}"
        client.set(key, "temporary")
        client.expire(key, 1)
        time.sleep(1.1)
        assert client.get(key) is None

    def test_delete(self, client: GlideClient):
        """DEL removes a key."""
        key = f"test:del:{uuid.uuid4().hex[:8]}"
        client.set(key, "to-delete")
        client.delete([key])
        assert client.get(key) is None


class TestContainerConfiguration:
    """Test ValkeyContainer configuration options."""

    def test_connection_url_format(self, valkey):
        """Connection URL has correct format."""
        url = valkey.get_connection_url()
        assert url.startswith("valkey://")
        assert str(valkey.get_exposed_port()) in url

    def test_bundle_image(self):
        """with_bundle() switches to valkey-bundle image."""
        container = ValkeyContainer().with_bundle()
        assert "valkey-bundle" in container.image

    def test_version_pinning(self):
        """with_image_tag() pins the version."""
        container = ValkeyContainer().with_image_tag("8.1.1")
        assert container.image == "valkey/valkey:8.1.1"

    def test_bundle_with_version(self):
        """Bundle and version can be combined."""
        container = ValkeyContainer().with_bundle().with_image_tag("9.1.0")
        assert container.image == "valkey/valkey-bundle:9.1.0"


class TestPasswordAuth:
    """Test password-authenticated containers."""

    def test_authenticated_connection(self):
        """Container with password requires credentials."""
        with ValkeyContainer().with_password("test-pass-123") as valkey:
            config = GlideClientConfiguration(
                [NodeAddress(valkey.get_host(), valkey.get_exposed_port())],
                credentials=ServerCredentials(password="test-pass-123"),
            )
            client = GlideClient.create(config)
            assert client.ping() == b"PONG"
            client.close()

    def test_connection_url_includes_password(self):
        """Connection URL includes password when set."""
        with ValkeyContainer().with_password("secret") as valkey:
            url = valkey.get_connection_url()
            assert ":secret@" in url


class TestVectorSearch:
    """Test Valkey Search module (requires bundle image)."""

    def test_create_and_search_vector_index(self, client: GlideClient):
        """FT.CREATE and FT.SEARCH work with the bundle image."""
        suffix = uuid.uuid4().hex[:8]
        index_name = f"idx:{suffix}"
        doc_prefix = f"doc:{suffix}:"

        # Create a FLAT vector index with 4 dimensions
        client.custom_command(
            [
                "FT.CREATE", index_name, "ON", "HASH",
                "PREFIX", "1", doc_prefix,
                "SCHEMA", "embedding", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32", "DIM", "4", "DISTANCE_METRIC", "COSINE",
            ]
        )

        # Insert two documents
        vec_a = struct.pack("4f", 1.0, 0.0, 0.0, 0.0)
        vec_b = struct.pack("4f", 0.0, 1.0, 0.0, 0.0)
        client.hset(f"{doc_prefix}a", {"embedding": vec_a})
        client.hset(f"{doc_prefix}b", {"embedding": vec_b})

        # Wait for indexing
        time.sleep(0.5)

        # KNN search for nearest neighbor to vec_a
        results = client.custom_command(
            [
                "FT.SEARCH", index_name,
                "*=>[KNN 1 @embedding $vec AS score]",
                "PARAMS", "2", "vec", vec_a,
                "RETURN", "1", "score",
            ]
        )
        # Results should be non-empty
        assert results is not None

        # Cleanup
        client.custom_command(["FT.DROPINDEX", index_name])
