from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import pytest

from main import (
    Settings,
    _checkpoint_key_with_marker,
    cleanup_sample,
    create_cache,
    create_valkey_client,
    create_checkpointer,
    create_store,
    run_cache_demo,
    run_checkpoint_demo,
    run_demo,
    run_store_demo,
)
from valkey import Valkey


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    suffix = uuid4().hex
    monkeypatch.setenv("VALKEY_CACHE_PREFIX", f"langchain-test-cache:{suffix}:")
    monkeypatch.setenv("VALKEY_STORE_COLLECTION", f"langchain_test_store_{suffix}")
    monkeypatch.setenv("VALKEY_STORE_NAMESPACE", f"langchain-test:{suffix}")
    return Settings.from_env()


@pytest.fixture
def test_run_id(settings: Settings) -> str:
    return settings.store_namespace.rsplit(":", 1)[-1]


def _cleanup_test_namespace(
    client: Valkey,
    settings: Settings,
    run_id: str,
) -> None:
    keys_to_delete: set[bytes] = set()
    for pattern in (
        f"{settings.cache_prefix}*",
        f"langgraph:{settings.store_namespace}:*",
        f"langgraph:{settings.store_namespace}/*",
    ):
        keys_to_delete.update(client.scan_iter(match=pattern))
    if keys_to_delete:
        client.delete(*keys_to_delete)
    cleanup_sample(client, settings=settings, run_id=run_id)


@pytest.fixture
def valkey_client(settings: Settings, test_run_id: str):
    client = Valkey.from_url(settings.valkey_url, decode_responses=False)
    try:
        client.ping()
    except Exception as exc:
        client.close()
        pytest.fail(f"Valkey is unavailable at {settings.valkey_url}: {exc}")

    try:
        _cleanup_test_namespace(client, settings, test_run_id)
        yield client
    finally:
        try:
            _cleanup_test_namespace(client, settings, test_run_id)
        finally:
            client.close()


def _scan_keys(client: Valkey, pattern: str) -> list[bytes]:
    return list(client.scan_iter(match=pattern))


def _index_exists(client: Valkey, index_name: str) -> bool:
    try:
        client.execute_command("FT.INFO", index_name)
    except Exception:
        return False
    return True


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (b"thread:{langchain-cookbook:demo}:default", True),
        (b"checkpoint:langchain-cookbook:demo:default", True),
        (b"thread:{langchain-cookbook:demo-extra}:default", False),
        (b"thread:{other-langchain-cookbook:demo}:default", False),
        (b"thread:{other:langchain-cookbook:demo}:default", False),
        (b"thread:{langchain-cookbook:demo-suffix}:default", False),
    ],
)
def test_checkpoint_cleanup_requires_an_exact_thread_id_boundary(
    key: bytes,
    expected: bool,
) -> None:
    assert (
        _checkpoint_key_with_marker(
            key,
            marker="langchain-cookbook:demo",
            exact_marker=True,
        )
        is expected
    )


def _seed_run_keys(client: Valkey, settings: Settings, run_id: str) -> None:
    client.set(
        f"{settings.cache_prefix}langchain-cookbook/{run_id}/answer",
        "cached",
    )
    client.hset(
        f"langgraph:{settings.store_namespace}:{run_id}/document",
        mapping={"value": "stored"},
    )
    client.set(
        f"thread:{{langchain-cookbook:{run_id}}}:default",
        "checkpoint",
    )


def test_cleanup_is_scoped_to_the_requested_run_by_default(
    settings: Settings,
    valkey_client: Valkey,
) -> None:
    _seed_run_keys(valkey_client, settings, "demo")
    _seed_run_keys(valkey_client, settings, "other-run")

    cleanup_sample(valkey_client, settings=settings)

    assert not _scan_keys(
        valkey_client,
        f"{settings.cache_prefix}langchain-cookbook/demo/*",
    )
    assert not _scan_keys(
        valkey_client,
        f"langgraph:{settings.store_namespace}:demo/*",
    )
    assert not _scan_keys(valkey_client, "*langchain-cookbook:demo*")
    assert _scan_keys(
        valkey_client,
        f"{settings.cache_prefix}langchain-cookbook/other-run/*",
    )
    assert _scan_keys(
        valkey_client,
        f"langgraph:{settings.store_namespace}:other-run/*",
    )
    assert _scan_keys(valkey_client, "*langchain-cookbook:other-run*")

    cleanup_sample(valkey_client, settings=settings, run_id="other-run")


def test_graph_checkpoint_persists_state_and_expires(
    settings: Settings, test_run_id: str, valkey_client: Valkey
) -> None:
    settings = replace(settings, checkpoint_ttl_seconds=120)
    thread_id = test_run_id

    with create_checkpointer(settings, client=valkey_client) as checkpointer:
        first = run_checkpoint_demo(
            checkpointer,
            thread_id=thread_id,
            message="first message",
        )

    assert first["messages"] == ["first message"]

    with create_checkpointer(settings, client=valkey_client) as checkpointer:
        resumed = run_checkpoint_demo(
            checkpointer,
            thread_id=thread_id,
            message="resumed message",
        )

    assert resumed["messages"] == ["first message", "resumed message"]

    checkpoint_keys = _scan_keys(valkey_client, f"*{thread_id}*")
    assert checkpoint_keys
    assert all(
        0 < valkey_client.ttl(key) <= settings.checkpoint_ttl_seconds
        for key in checkpoint_keys
    )


def test_cache_miss_then_hit_and_explicit_ttl(
    settings: Settings, test_run_id: str, valkey_client: Valkey
) -> None:
    cache = create_cache(settings, client=valkey_client)
    key = (("langchain-cookbook", test_run_id), f"answer-{test_run_id}")
    value = {"answer": "Valkey is fast."}

    first = run_cache_demo(cache, key=key, value=value)
    second = run_cache_demo(cache, key=key, value={"answer": "should not win"})

    assert first == {"hit": False, "value": value}
    assert second == {"hit": True, "value": value}

    short_ttl_key = (("langchain-cookbook", test_run_id), f"short-{test_run_id}")
    short_ttl = 3
    asyncio.run(
        cache.aset(
            {
                short_ttl_key: (
                    {"answer": "expires soon"},
                    short_ttl,
                )
            }
        )
    )

    cache_keys = _scan_keys(valkey_client, f"{settings.cache_prefix}*")
    short_key_suffix = f"/{short_ttl_key[1]}".encode()
    matching_keys = [key for key in cache_keys if key.endswith(short_key_suffix)]
    assert len(matching_keys) == 1
    assert 0 < valkey_client.ttl(matching_keys[0]) <= short_ttl


def test_store_search_returns_semantically_related_document_and_isolates_namespace(
    settings: Settings, test_run_id: str, valkey_client: Valkey
) -> None:
    team_a = (settings.store_namespace, f"team-a-{test_run_id}")
    team_b = (settings.store_namespace, f"team-b-{test_run_id}")

    with create_store(
        settings,
        client=valkey_client,
    ) as store:
        team_a_results = run_store_demo(
            store,
            namespace=team_a,
            query="I forgot my password",
            documents=[
                (
                    f"password-a-{test_run_id}",
                    {
                        "text": "How do I reset my password?",
                        "answer": "Team A password instructions",
                    },
                )
            ],
        )
        team_b_results = run_store_demo(
            store,
            namespace=team_b,
            query="I forgot my password",
            documents=[
                (
                    f"password-b-{test_run_id}",
                    {
                        "text": "How do I reset my password?",
                        "answer": "Team B password instructions",
                    },
                )
            ],
        )

        direct_team_a_results = store.search(
            team_a,
            query="I forgot my password",
            limit=5,
        )

    assert [result.value["answer"] for result in team_a_results] == [
        "Team A password instructions"
    ]
    assert [result.value["answer"] for result in team_b_results] == [
        "Team B password instructions"
    ]
    assert [result.value["answer"] for result in direct_team_a_results] == [
        "Team A password instructions"
    ]
    store_key = "langgraph:" + "/".join(team_a + (f"password-a-{test_run_id}",))
    store_ttl = valkey_client.ttl(store_key)
    assert 0 < store_ttl <= int(settings.store_ttl_minutes * 60)


def test_environment_overrides_are_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_url = os.getenv("VALKEY_URL", "valkey://127.0.0.1:6379")
    monkeypatch.delenv("VALKEY_URL", raising=False)
    monkeypatch.setenv("VALKEY_HOST", "127.0.0.1")
    monkeypatch.setenv("VALKEY_PORT", "6391")
    monkeypatch.setenv("CHECKPOINT_TTL_SECONDS", "23")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "31")
    monkeypatch.setenv("STORE_TTL_MINUTES", "47")
    monkeypatch.setenv("VALKEY_SOCKET_TIMEOUT", "7.5")
    monkeypatch.setenv("VALKEY_CACHE_PREFIX", "override-cache:")
    monkeypatch.setenv("VALKEY_STORE_COLLECTION", "override_store")
    monkeypatch.setenv("VALKEY_STORE_NAMESPACE", "override-namespace")

    settings = Settings.from_env()

    assert settings.valkey_url == "valkey://127.0.0.1:6391"
    assert settings.checkpoint_ttl_seconds == 23
    assert settings.cache_ttl_seconds == 31
    assert settings.store_ttl_minutes == 47
    assert settings.socket_timeout == 7.5
    assert settings.cache_prefix == "override-cache:"
    assert settings.store_collection_name == "override_store"
    assert settings.store_namespace == "override-namespace"

    runtime_settings = replace(settings, valkey_url=runtime_url)
    client = create_valkey_client(runtime_settings)
    try:
        client.ping()
    except Exception as exc:
        client.close()
        pytest.fail(f"Valkey is unavailable at {settings.valkey_url}: {exc}")

    try:
        assert (
            client.connection_pool.connection_kwargs["socket_timeout"]
            == settings.socket_timeout
        )
        with create_checkpointer(settings, client=client) as checkpointer:
            assert checkpointer.ttl == settings.checkpoint_ttl_seconds

        cache = create_cache(settings, client=client)
        assert cache.ttl == settings.cache_ttl_seconds
        assert cache.prefix == settings.cache_prefix

        with create_store(
            settings,
            client=client,
        ) as store:
            assert store.ttl_config == {"default_ttl": settings.store_ttl_minutes}
            assert store.collection_name == settings.store_collection_name
    finally:
        cleanup_sample(client, settings=runtime_settings, run_id="demo")
        client.close()


def test_cleanup_runs_after_failure_and_second_run_is_idempotent(
    settings: Settings,
    test_run_id: str,
    valkey_client: Valkey,
) -> None:
    run_id = f"failed-demo-{test_run_id}"
    sentinel_key = f"unrelated:{test_run_id}"
    unrelated_store_key = f"langgraph:unrelated:{test_run_id}"
    valkey_client.set(sentinel_key, "must-survive")
    valkey_client.hset(unrelated_store_key, mapping={"value": "must-survive"})

    try:
        with pytest.raises(RuntimeError, match="cache"):
            run_demo(
                settings,
                client=valkey_client,
                run_id=run_id,
                fail_at="cache",
            )

        assert not _scan_keys(valkey_client, f"*{run_id}*")
        assert not _scan_keys(valkey_client, f"{settings.cache_prefix}*")
        assert not _scan_keys(
            valkey_client, f"langgraph:{settings.store_namespace}:{run_id}:*"
        )
        assert _index_exists(valkey_client, settings.store_collection_name)
        assert valkey_client.get(sentinel_key) == b"must-survive"
        assert valkey_client.hget(unrelated_store_key, "value") == b"must-survive"

        successful_run_id = f"successful-demo-{test_run_id}"
        first_run = run_demo(
            settings,
            client=valkey_client,
            run_id=successful_run_id,
        )
        second_run = run_demo(
            settings,
            client=valkey_client,
            run_id=successful_run_id,
        )
        assert first_run["run_id"] == second_run["run_id"] == successful_run_id
        cleanup_sample(
            valkey_client,
            settings=settings,
            run_id=successful_run_id,
        )
        cleanup_sample(
            settings.valkey_url,
            settings=settings,
            run_id=successful_run_id,
        )

        assert not _scan_keys(valkey_client, f"*{successful_run_id}*")
        assert not _scan_keys(
            valkey_client,
            f"langgraph:{settings.store_namespace}:*",
        )
        assert _index_exists(valkey_client, settings.store_collection_name)
        assert not _scan_keys(valkey_client, f"*{run_id}*")
        assert not _scan_keys(valkey_client, f"{settings.cache_prefix}*")
        assert valkey_client.hget(unrelated_store_key, "value") == b"must-survive"
        assert valkey_client.get(sentinel_key) == b"must-survive"
    finally:
        valkey_client.delete(sentinel_key)
        valkey_client.delete(unrelated_store_key)
