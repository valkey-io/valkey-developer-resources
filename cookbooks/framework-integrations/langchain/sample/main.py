from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from cleanup import _checkpoint_key_with_marker, cleanup_sample
from langgraph.graph import MessagesState, StateGraph
from langgraph_checkpoint_aws import ValkeyCache, ValkeySaver, ValkeyStore
from langchain_core.messages import HumanMessage
from resources import (
    DeterministicEmbeddings,
    Settings,
    _validate_run_id,
    create_cache,
    create_checkpointer,
    create_store,
    create_valkey_client,
)
from valkey import Valkey


_LOGGER = logging.getLogger(__name__)
__all__ = [
    "DeterministicEmbeddings",
    "Settings",
    "_checkpoint_key_with_marker",
    "cleanup_sample",
    "create_cache",
    "create_checkpointer",
    "create_store",
    "create_valkey_client",
    "run_cache_demo",
    "run_checkpoint_demo",
    "run_demo",
    "run_store_demo",
]


def run_checkpoint_demo(
    checkpointer: ValkeySaver,
    thread_id: str,
    message: str,
) -> dict[str, list[str]]:
    builder = StateGraph(MessagesState)

    def keep_state(_: MessagesState) -> dict[str, Any]:
        return {}

    builder.add_node("keep_state", keep_state)
    builder.set_entry_point("keep_state")
    builder.set_finish_point("keep_state")
    graph = builder.compile(checkpointer=checkpointer)

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }
    result = graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        config,
    )
    return {
        "messages": [str(item.content) for item in result["messages"]],
    }


def run_cache_demo(
    cache: ValkeyCache,
    key: tuple[tuple[str, ...], str],
    value: Any,
) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        cached_values = await cache.aget([key])
        if key in cached_values:
            return {"hit": True, "value": cached_values[key]}

        await cache.aset({key: (value, None)})
        return {"hit": False, "value": value}

    return asyncio.run(run())


def run_store_demo(
    store: ValkeyStore,
    namespace: tuple[str, ...],
    query: str,
    documents: list[tuple[str, dict[str, Any]]],
) -> Any:
    for key, value in documents:
        store.put(namespace, key, value)
    return store.search(namespace, query=query, limit=5)


def _raise_if_requested(stage: str, fail_at: str | None) -> None:
    if fail_at == stage:
        raise RuntimeError(f"demo failed after {stage} stage")


def run_demo(
    settings: Settings,
    client: Valkey | None = None,
    embeddings: Any | None = None,
    run_id: str = "demo",
    fail_at: str | None = None,
) -> dict[str, Any]:
    valid_stages = {"checkpoint", "cache", "store"}
    if fail_at is not None and fail_at not in valid_stages:
        raise ValueError(f"fail_at must be one of {sorted(valid_stages)}")
    _validate_run_id(run_id)

    owned_client = client is None
    valkey_client = client or create_valkey_client(settings)
    try:
        with (
            create_checkpointer(
                settings,
                client=valkey_client,
            ) as checkpointer,
            create_cache(
                settings,
                client=valkey_client,
            ) as cache,
            create_store(
                settings,
                client=valkey_client,
                embeddings=embeddings,
            ) as store,
        ):
            checkpoint = run_checkpoint_demo(
                checkpointer,
                thread_id=f"{settings.store_namespace}:{run_id}",
                message=f"Run {run_id}: I forgot my password.",
            )
            _raise_if_requested("checkpoint", fail_at)

            cache_key = (
                (settings.store_namespace, run_id),
                f"answer-{run_id}",
            )
            cache_result = run_cache_demo(
                cache,
                key=cache_key,
                value={"answer": "Valkey is fast."},
            )
            _raise_if_requested("cache", fail_at)

            store_namespace = (f"{settings.store_namespace}:{run_id}",)
            store_result = run_store_demo(
                store,
                namespace=store_namespace,
                query="I forgot my password.",
                documents=[
                    (
                        f"password-{run_id}",
                        {
                            "text": "How do I reset my password?",
                            "answer": "Use the password reset page.",
                        },
                    )
                ],
            )
            _raise_if_requested("store", fail_at)

            return {
                "run_id": run_id,
                "checkpoint": checkpoint,
                "cache": cache_result,
                "store": store_result,
            }
    finally:
        stage_exception_active = sys.exc_info()[0] is not None
        cleanup_error: Exception | None = None
        try:
            cleanup_sample(
                valkey_client,
                settings=settings,
                run_id=run_id,
            )
        except Exception as exc:
            if stage_exception_active:
                _LOGGER.exception("Sample cleanup failed after a demo error")
            else:
                cleanup_error = exc
        finally:
            if owned_client:
                try:
                    valkey_client.close()
                except Exception:
                    if stage_exception_active:
                        _LOGGER.exception("Closing the sample Valkey client failed")
                    elif cleanup_error is None:
                        raise
                    else:
                        _LOGGER.exception("Closing the sample Valkey client failed")
        if cleanup_error is not None:
            raise cleanup_error


def main() -> None:
    settings = Settings.from_env()
    result = run_demo(settings)
    print("checkpoint:", result["checkpoint"])
    print("cache:", result["cache"])
    print("semantic search:", result["store"])


if __name__ == "__main__":
    main()
