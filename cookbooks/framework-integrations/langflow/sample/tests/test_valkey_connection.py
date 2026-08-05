"""Integration tests verifying Valkey connectivity and operations used by Langflow.

These tests validate the Valkey operations that Langflow's components use:
- Basic connectivity (PING)
- List operations (chat memory storage pattern)
- Hash + search module operations (vector store pattern)
"""

import json

import pytest
import valkey


@pytest.mark.integration
class TestValkeyConnection:
    """Test basic Valkey connectivity."""

    def test_ping(self, valkey_client: valkey.Valkey) -> None:
        """Valkey server responds to PING."""
        assert valkey_client.ping() is True

    def test_info(self, valkey_client: valkey.Valkey) -> None:
        """Valkey server returns info with version."""
        info = valkey_client.info("server")
        assert "valkey_version" in info or "redis_version" in info


@pytest.mark.integration
class TestChatMemoryPattern:
    """Test the List-based chat memory pattern used by Langflow's Valkey Chat Memory."""

    def test_store_and_retrieve_messages(
        self, valkey_client: valkey.Valkey, clean_prefix: str
    ) -> None:
        """Store chat messages as JSON in a List (mimics RedisChatMessageHistory)."""
        key = f"{clean_prefix}session-1"

        # Store messages as Langflow/LangChain does
        messages = [
            {"type": "human", "content": "Hello, who are you?"},
            {"type": "ai", "content": "I am a helpful assistant."},
            {"type": "human", "content": "What is Valkey?"},
            {"type": "ai", "content": "Valkey is an open-source key/value datastore."},
        ]

        for msg in messages:
            valkey_client.rpush(key, json.dumps(msg))

        # Retrieve all messages
        stored = valkey_client.lrange(key, 0, -1)
        assert len(stored) == 4

        parsed = [json.loads(m) for m in stored]
        assert parsed[0]["type"] == "human"
        assert parsed[0]["content"] == "Hello, who are you?"
        assert parsed[3]["type"] == "ai"

    def test_session_isolation(
        self, valkey_client: valkey.Valkey, clean_prefix: str
    ) -> None:
        """Different session IDs maintain separate message histories."""
        key_a = f"{clean_prefix}session-a"
        key_b = f"{clean_prefix}session-b"

        valkey_client.rpush(key_a, json.dumps({"type": "human", "content": "A"}))
        valkey_client.rpush(key_b, json.dumps({"type": "human", "content": "B"}))

        assert valkey_client.llen(key_a) == 1
        assert valkey_client.llen(key_b) == 1

        msg_a = json.loads(valkey_client.lrange(key_a, 0, -1)[0])
        msg_b = json.loads(valkey_client.lrange(key_b, 0, -1)[0])
        assert msg_a["content"] == "A"
        assert msg_b["content"] == "B"

    def test_clear_session(
        self, valkey_client: valkey.Valkey, clean_prefix: str
    ) -> None:
        """Clearing a session removes all messages for that session."""
        key = f"{clean_prefix}session-clear"

        valkey_client.rpush(key, json.dumps({"type": "human", "content": "test"}))
        assert valkey_client.llen(key) == 1

        valkey_client.delete(key)
        assert valkey_client.llen(key) == 0


@pytest.mark.integration
class TestVectorStorePattern:
    """Test the Hash + FT.SEARCH pattern used by Langflow's Valkey Vector Store."""

    def test_search_module_loaded(self, valkey_client: valkey.Valkey) -> None:
        """Verify the search module is available (required for vector store)."""
        modules = valkey_client.module_list()
        module_names = [m["name"] for m in modules]
        assert "search" in module_names, (
            f"search module not loaded. Available: {module_names}. "
            "Use valkey/valkey-bundle image."
        )

    def test_create_and_drop_index(self, valkey_client: valkey.Valkey) -> None:
        """Create a vector index and drop it (lifecycle test)."""
        index_name = "test-langflow-idx"

        # Drop if exists from a previous failed run
        try:
            valkey_client.execute_command("FT.DROPINDEX", index_name)
        except valkey.ResponseError as e:
            if "Unknown index name" not in str(e) and "not found" not in str(e):
                raise

        # Create index on Hash with a vector field (TAG for metadata, VECTOR for embeddings)
        try:
            valkey_client.execute_command(
                "FT.CREATE",
                index_name,
                "ON",
                "HASH",
                "PREFIX",
                "1",
                "test:doc:",
                "SCHEMA",
                "content",
                "TAG",
                "content_vector",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                "4",
                "DISTANCE_METRIC",
                "COSINE",
            )

            # Verify index exists
            info = valkey_client.execute_command("FT.INFO", index_name)
            assert info is not None
        finally:
            # Clean up
            try:
                valkey_client.execute_command("FT.DROPINDEX", index_name)
            except valkey.ResponseError:
                pass

    def test_store_and_search_vectors(self, valkey_host: str, valkey_port: int) -> None:
        """Store documents with vectors and perform KNN search."""
        import struct

        # Use a non-decoding client for binary vector data
        client = valkey.Valkey(
            host=valkey_host, port=valkey_port, decode_responses=False
        )

        index_name = "test-langflow-search"

        try:
            # Clean up from previous runs
            try:
                client.execute_command("FT.DROPINDEX", index_name)
            except valkey.ResponseError:
                pass
            # Also clean up any leftover keys
            for key in client.scan_iter(b"test:vec:*"):
                client.delete(key)

            # Create index (TAG for metadata fields in valkey-search)
            client.execute_command(
                "FT.CREATE",
                index_name,
                "ON",
                "HASH",
                "PREFIX",
                "1",
                "test:vec:",
                "SCHEMA",
                "content",
                "TAG",
                "content_vector",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                "4",
                "DISTANCE_METRIC",
                "COSINE",
            )

            # Store documents with fake 4-dimensional vectors
            vectors = [
                ([1.0, 0.0, 0.0, 0.0], "Valkey is a fast database"),
                ([0.0, 1.0, 0.0, 0.0], "Python is a programming language"),
                ([0.9, 0.1, 0.0, 0.0], "Valkey supports vector search"),
            ]

            for i, (vec, content) in enumerate(vectors):
                vec_bytes = struct.pack(f"{len(vec)}f", *vec)
                client.hset(
                    f"test:vec:{i}",
                    mapping={"content": content, "content_vector": vec_bytes},
                )

            # Search for vectors similar to [1.0, 0.0, 0.0, 0.0]
            query_vec = struct.pack("4f", 1.0, 0.0, 0.0, 0.0)
            results = client.execute_command(
                "FT.SEARCH",
                index_name,
                "*=>[KNN 2 @content_vector $BLOB AS score]",
                "PARAMS",
                "2",
                "BLOB",
                query_vec,
                "DIALECT",
                "2",
            )

            # Results format: [total_count, key1, fields1, key2, fields2, ...]
            assert results[0] >= 2
            # First result should be the exact match or closest
            first_fields = dict(zip(results[2][::2], results[2][1::2]))
            assert b"Valkey" in first_fields[b"content"]
        finally:
            # Clean up index and keys
            try:
                client.execute_command("FT.DROPINDEX", index_name)
            except valkey.ResponseError:
                pass
            for key in client.scan_iter(b"test:vec:*"):
                client.delete(key)
            client.close()
