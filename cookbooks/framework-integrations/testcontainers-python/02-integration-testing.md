# Integration Testing

> Build pytest fixtures that give each test a fresh Valkey instance — isolated, repeatable, and CI-friendly.

**Intermediate** · Python · ~10 min

**Who is this for:** Python developers writing integration tests that need a real Valkey backend without shared state between tests or flaky port conflicts in CI.

## Why TestContainers for Testing

Traditional approaches have drawbacks:

| Approach | Problem |
| -------- | ------- |
| Shared test server | Tests interfere with each other; flushdb between tests is fragile |
| Docker Compose in CI | Extra setup step; port conflicts in parallel jobs |
| Mocking the client | Tests pass but miss real Valkey behavior (TTL, atomicity, etc.) |

TestContainers solves all three: each test session gets its own Valkey instance on a random port, started and stopped automatically by pytest.

## Prerequisites

- Docker or Podman installed and running
- Python 3.9+
- Dependencies installed (see [Getting Started](01-getting-started.md))

## Step 1: Create a Session-Scoped Fixture

A single Valkey container shared across all tests in a session (fast startup, tests still isolated by key prefix):

```python
import pytest
from testcontainers.community.valkey import ValkeyContainer
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress


@pytest.fixture(scope="session")
def valkey_container():
    """Start a Valkey container for the entire test session."""
    with ValkeyContainer().with_bundle().with_image_tag("9.1.0") as container:
        yield container


@pytest.fixture(scope="session")
def valkey_client(valkey_container):
    """Create a GLIDE client connected to the test container."""
    config = GlideClientConfiguration(
        [NodeAddress(valkey_container.get_host(), valkey_container.get_exposed_port())]
    )
    client = GlideClient.create(config)
    yield client
    client.close()
```

## Step 2: Write Isolated Tests

Each test uses unique keys to avoid interference:

```python
import uuid


class TestValkeyOperations:
    def test_set_and_get(self, valkey_client):
        key = f"test:{uuid.uuid4().hex[:8]}"
        valkey_client.set(key, "hello")
        assert valkey_client.get(key) == "hello"

    def test_expiration(self, valkey_client):
        import time

        key = f"test:{uuid.uuid4().hex[:8]}"
        valkey_client.set(key, "ephemeral")
        valkey_client.expire(key, 1)
        time.sleep(1.1)
        assert valkey_client.get(key) is None

    def test_increment(self, valkey_client):
        key = f"counter:{uuid.uuid4().hex[:8]}"
        valkey_client.set(key, "0")
        valkey_client.incr(key)
        valkey_client.incr(key)
        assert valkey_client.get(key) == "2"
```

## Step 3: Test with Password Authentication

Verify your application handles authenticated connections correctly:

```python
@pytest.fixture(scope="module")
def authed_container():
    """Valkey container with password authentication."""
    with ValkeyContainer().with_password("test-secret-123") as container:
        yield container


def test_authenticated_connection(authed_container):
    from glide_sync import ServerCredentials

    config = GlideClientConfiguration(
        [NodeAddress(authed_container.get_host(), authed_container.get_exposed_port())],
        credentials=ServerCredentials(password="test-secret-123"),
    )
    client = GlideClient.create(config)
    assert client.ping() == "PONG"
    client.close()
```

## Step 4: Test Vector Search (Bundle Image)

If your application uses Valkey Search, test against the bundle image:

```python
import struct


def test_vector_index(valkey_client):
    """Verify FT.CREATE and FT.SEARCH work with the bundle image."""
    index_name = f"idx:{uuid.uuid4().hex[:8]}"

    # Create a vector index
    valkey_client.custom_command(
        [
            "FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", f"doc:{index_name}:",
            "SCHEMA", "embedding", "VECTOR", "FLAT", "6",
            "TYPE", "FLOAT32", "DIM", "4", "DISTANCE_METRIC", "COSINE",
        ]
    )

    # Insert a document with a 4-dim vector
    vector_bytes = struct.pack("4f", 1.0, 0.0, 0.0, 0.0)
    valkey_client.hset(f"doc:{index_name}:1", {"embedding": vector_bytes})

    # Search (allow indexing time)
    import time
    time.sleep(0.5)

    results = valkey_client.custom_command(
        [
            "FT.SEARCH", index_name, "*=>[KNN 1 @embedding $vec AS score]",
            "PARAMS", "2", "vec", vector_bytes, "RETURN", "1", "score",
        ]
    )
    assert results is not None

    # Cleanup index
    valkey_client.custom_command(["FT.DROPINDEX", index_name])
```

## Step 5: Parallel Test Safety

TestContainers assigns random ports, so parallel pytest workers (`pytest-xdist`) each get their own container without conflicts:

```bash
pip install pytest-xdist
pytest -n 4 test_valkey.py
```

Each worker's `session`-scoped fixture creates a separate container. No coordination needed.

## Project Structure

```text
your-project/
├── src/
│   └── your_app/
│       └── cache.py          # Your code that talks to Valkey
├── tests/
│   ├── conftest.py           # Fixtures (valkey_container, valkey_client)
│   └── test_cache.py         # Integration tests
└── requirements-test.txt     # testcontainers[valkey], valkey-glide-sync, pytest
```

## CI Configuration (GitHub Actions)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-test.txt
      - run: pytest tests/ -v
```

No Valkey service container needed in CI — TestContainers starts its own. The only requirement is that Docker is available on the runner (GitHub Actions `ubuntu-latest` includes Docker).

## Tips

- **Scope wisely:** Use `scope="session"` for speed (one container per run) or `scope="function"` for full isolation (one container per test — slower).
- **Unique keys:** Always prefix keys with a random value to prevent test interference when sharing a container.
- **Pin versions:** Use `.with_image_tag("9.1.0")` in CI for reproducible builds. Never use `:latest` in automated tests.
- **Ryuk cleanup:** TestContainers runs a sidecar container (Ryuk) that garbage-collects orphaned containers if your test process crashes.

---

[← 01 - Getting Started](01-getting-started.md) | [README](README.md)
