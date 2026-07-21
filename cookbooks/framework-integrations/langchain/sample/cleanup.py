from __future__ import annotations

from typing import Any

from resources import (
    Settings,
    _index_owner_key,
    _validate_run_id,
    create_valkey_client,
)
from valkey import Valkey
from valkey.exceptions import ResponseError


_CHECKPOINT_KEY_PREFIXES = {
    "checkpoint",
    "checkpoints",
    "checkpoint_write",
    "checkpoint_writes",
    "write",
    "writes",
    "thread",
    "threads",
}


def _delete_keys(client: Valkey, keys: set[Any]) -> None:
    key_list = list(keys)
    for start in range(0, len(key_list), 100):
        client.delete(*key_list[start : start + 100])


def _key_text(key: Any) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8", errors="replace")
    return str(key)


def _checkpoint_key_with_marker(
    key: Any,
    marker: str,
    exact_marker: bool,
) -> bool:
    key_text = _key_text(key)
    key_family = key_text.split(":", 1)[0]
    if key_family not in _CHECKPOINT_KEY_PREFIXES:
        return False
    if not exact_marker:
        return marker in key_text

    for marker_prefix in (f"{key_family}:{{", f"{key_family}:"):
        expected_prefix = marker_prefix + marker
        if not key_text.startswith(expected_prefix):
            continue
        marker_end = len(expected_prefix)
        if marker_prefix.endswith("{"):
            if marker_end >= len(key_text) or key_text[marker_end] != "}":
                continue
            marker_end += 1
        if marker_end == len(key_text) or key_text[marker_end] in ":/":
            return True
    return False


def _drop_sample_index(client: Valkey, index_name: str) -> None:
    try:
        client.execute_command("FT.DROPINDEX", index_name)
    except ResponseError as exc:
        error_text = str(exc).lower()
        if not any(
            phrase in error_text
            for phrase in (
                "unknown index",
                "no such index",
                "does not exist",
                "not found",
            )
        ):
            raise


def _store_key_patterns(store_namespace: str) -> tuple[str, str]:
    store_prefix = f"langgraph:{store_namespace}"
    return f"{store_prefix}:*", f"{store_prefix}/*"


def cleanup_sample(
    resource: Valkey | str,
    settings: Settings,
    run_id: str = "demo",
) -> None:
    """Delete only keys owned by one sample run.

    The default targets the same ``demo`` run used by ``run_demo``. There is
    intentionally no global cleanup mode because a shared Valkey endpoint may
    contain data from other runs or applications.
    """
    _validate_run_id(run_id)

    owned_client = isinstance(resource, str)
    client = create_valkey_client(settings) if owned_client else resource
    try:
        index_owner_key = _index_owner_key(settings.store_collection_name)
        index_is_owned = bool(client.exists(index_owner_key))
        keys_to_delete: set[Any] = set()
        store_patterns = _store_key_patterns(settings.store_namespace)
        store_keys: set[Any] = set()
        for pattern in store_patterns:
            store_keys.update(client.scan_iter(match=pattern))

        cache_namespace = f"{settings.cache_prefix}langchain-cookbook/{run_id}"
        if settings.cache_prefix:
            for key in client.scan_iter(match=f"{settings.cache_prefix}*"):
                key_text = _key_text(key)
                if key_text == cache_namespace or key_text.startswith(
                    cache_namespace + "/"
                ):
                    keys_to_delete.add(key)

        run_store_namespace = f"langgraph:{settings.store_namespace}:{run_id}"
        for key in store_keys:
            key_text = _key_text(key)
            if key_text == run_store_namespace or key_text.startswith(
                (run_store_namespace + "/", run_store_namespace + ":")
            ):
                keys_to_delete.add(key)

        checkpoint_marker = f"langchain-cookbook:{run_id}"
        for key in client.scan_iter(match="*"):
            if _checkpoint_key_with_marker(
                key,
                checkpoint_marker,
                exact_marker=True,
            ):
                keys_to_delete.add(key)

        _delete_keys(client, keys_to_delete)

        remaining_collection_keys = set(client.scan_iter(match="langgraph:*"))
        if not remaining_collection_keys and index_is_owned:
            _drop_sample_index(client, settings.store_collection_name)
            client.delete(index_owner_key)
    finally:
        if owned_client:
            client.close()
