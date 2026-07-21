"""Behavior and lifecycle tests for the OpenAI + Valkey sample."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from glide import glide_json
from glide_shared.exceptions import RequestError

import common
import getting_started
from common import (
    cleanup,
    connection_settings,
    create_client,
    embedding_dimension,
    field_text,
    LOCAL_EMBEDDING_DIM,
    vector_similarity,
)
from getting_started import INDEX_NAME as GETTING_STARTED_INDEX
from getting_started import run_demo as run_getting_started
from vector_search import (
    DOCUMENTS,
    INDEX_NAME as VECTOR_INDEX,
    create_hnsw_index,
    index_documents,
    search,
)


@pytest.fixture(autouse=True)
def disable_openai_for_tests(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")


def test_environment_overrides_are_read_at_client_creation(monkeypatch):
    monkeypatch.setenv("VALKEY_HOST", "127.0.0.1")
    monkeypatch.setenv("VALKEY_PORT", "6381")
    assert connection_settings() == ("127.0.0.1", 6381)


def test_environment_overrides_are_applied_to_glide_config(monkeypatch):
    captured = {}

    async def fake_create(config):
        captured["config"] = config
        return object()

    monkeypatch.setenv("VALKEY_HOST", "127.0.0.1")
    monkeypatch.setenv("VALKEY_PORT", "6381")
    monkeypatch.setattr(common.GlideClient, "create", fake_create)

    asyncio.run(common.create_client())

    config = captured["config"]
    assert config.addresses[0].host == "127.0.0.1"
    assert config.addresses[0].port == 6381
    assert config.request_timeout == 5000
    assert config.advanced_config.connection_timeout == 5000


def test_dotenv_file_provides_connection_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VALKEY_HOST", raising=False)
    monkeypatch.delenv("VALKEY_PORT", raising=False)
    (tmp_path / ".env").write_text("VALKEY_HOST=192.0.2.10\nVALKEY_PORT=6381\n")

    assert connection_settings() == ("192.0.2.10", 6381)


def test_openai_embedding_dimension_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIM", "32")

    assert embedding_dimension() == 32


def test_explicit_empty_api_key_overrides_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert embedding_dimension() == LOCAL_EMBEDDING_DIM


def test_search_response_fields_support_vector_score_encoding():
    byte_fields = {b"title": b"Valkey", b"vector_score": b"0.25"}
    text_fields = {"title": "Valkey", "score": "0.25"}

    assert field_text(byte_fields, "title") == "Valkey"
    assert field_text(text_fields, "title") == "Valkey"
    assert vector_similarity(byte_fields) == 0.75
    assert vector_similarity(text_fields) == 0.75


def test_hybrid_search_rejects_invalid_k(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(ValueError, match="k"):
        asyncio.run(search(object(), "query", k=0))


def test_drop_index_does_not_hide_real_request_errors(monkeypatch):
    async def fail(*_args):
        raise RequestError("server rejected the request")

    monkeypatch.setattr(common.ft, "dropindex", fail)

    with pytest.raises(RequestError, match="server rejected"):
        asyncio.run(common.drop_index(object(), "test-index"))


def test_drop_index_ignores_missing_index_errors(monkeypatch):
    async def fail(*_args):
        raise RequestError(
            "Index: with name 'test-index' not found in database 0"
        )

    monkeypatch.setattr(common.ft, "dropindex", fail)
    asyncio.run(common.drop_index(object(), "test-index"))


def test_openai_embedder_is_reused_and_closed(monkeypatch):
    class FakeOpenAI:
        instances = []

        def __init__(self, **_kwargs):
            self.closed = False
            self.embeddings = self
            self.options = _kwargs
            self.calls = []
            self.instances.append(self)

        def create(self, input, model, **_kwargs):
            self.calls.append((input, model, _kwargs))
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[float(index)])
                    for index, _ in enumerate(input)
                ]
            )

        def close(self):
            self.closed = True

    common.close_embedder()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EMBED_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIM", "32")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    common.embed(["first"])
    common.embed(["second"])

    assert len(FakeOpenAI.instances) == 1
    assert FakeOpenAI.instances[0].options == {
        "api_key": "test-key",
        "timeout": 10.0,
        "max_retries": 1,
    }
    assert FakeOpenAI.instances[0].calls[0][1:] == (
        "test-model",
        {"dimensions": 32},
    )
    common.close_embedder()
    assert FakeOpenAI.instances[0].closed


def test_partial_indexing_keys_are_cleaned_up(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    original_set = getting_started.glide_json.set
    keys_written = 0

    async def fail_on_second_write(client, key, path, value):
        nonlocal keys_written
        keys_written += 1
        if keys_written == 2:
            raise RuntimeError("intentional indexing failure")
        return await original_set(client, key, path, value)

    monkeypatch.setattr(getting_started.glide_json, "set", fail_on_second_write)

    async def exercise():
        client = await create_client()
        keys = []
        try:
            await getting_started.create_index(client)
            with pytest.raises(RuntimeError, match="indexing failure"):
                await getting_started.index_documents(
                    client, getting_started.DOCUMENTS, keys
                )
            assert keys == ["doc:1", "doc:2"]
        finally:
            try:
                await cleanup(client, getting_started.INDEX_NAME, keys)
            finally:
                if keys:
                    assert await client.exists(keys) == 0
                await client.close()

    asyncio.run(exercise())


def test_getting_started_is_idempotent_without_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    asyncio.run(run_getting_started())
    asyncio.run(run_getting_started())


def test_hybrid_search_scopes_results(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    async def exercise():
        client = await create_client()
        keys = []
        try:
            await create_hnsw_index(client)
            keys = await index_documents(client, DOCUMENTS)
            results = await search(client, "in-memory database", genre="tech")
            assert results
            assert all(result["genre"] == "tech" for result in results)
        finally:
            try:
                await cleanup(client, VECTOR_INDEX, keys)
            finally:
                await client.close()

    asyncio.run(exercise())


def test_cleanup_runs_after_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    async def exercise():
        client = await create_client()
        key = "doc:failure-cleanup"
        try:
            await glide_json.set(client, key, "$", '{"text":"temporary"}')
            with pytest.raises(RuntimeError):
                try:
                    raise RuntimeError("intentional test failure")
                finally:
                    await cleanup(client, GETTING_STARTED_INDEX, [key])
        finally:
            assert await client.exists([key]) == 0
            await client.close()

    asyncio.run(exercise())
