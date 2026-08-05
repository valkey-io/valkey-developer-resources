"""Shared constants and utilities for Open WebUI + Valkey cookbook samples."""

import struct
import time


# Open WebUI collection naming conventions
COLLECTION_PREFIX = "open_webui"
COLLECTION_NAME = "demo_knowledge_base"
INDEX_NAME = f"idx:{COLLECTION_PREFIX}:{COLLECTION_NAME}"
KEY_PREFIX = f"{COLLECTION_PREFIX}:{COLLECTION_NAME}:"
DIMENSION = 128

# Test-specific overrides (used by conftest.py and tests)
TEST_COLLECTION_PREFIX = "test_owui"
TEST_COLLECTION_NAME = "test_collection"
TEST_INDEX_NAME = f"idx:{TEST_COLLECTION_PREFIX}:{TEST_COLLECTION_NAME}"
TEST_KEY_PREFIX = f"{TEST_COLLECTION_PREFIX}:{TEST_COLLECTION_NAME}:"


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32 (matches Open WebUI's _vector_to_bytes)."""
    return struct.pack(f"<{len(vector)}f", *vector)


def wait_for_indexing(client, index_name: str, expected: int, timeout: float = 5.0) -> None:
    """Poll FT.INFO until num_docs reaches expected count.

    Replaces flaky time.sleep() — works reliably under CI load.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = client.execute_command("FT.INFO", index_name)
        # FT.INFO returns a flat list: [..., "num_docs", <count>, ...]
        for i, item in enumerate(info):
            val = item.decode() if isinstance(item, bytes) else str(item)
            if val == "num_docs":
                num_docs = int(info[i + 1])
                if num_docs >= expected:
                    return
                break
        time.sleep(0.05)
    raise TimeoutError(
        f"Index '{index_name}' did not reach {expected} docs within {timeout}s"
    )
