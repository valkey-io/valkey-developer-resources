# Getting Started

> Launch a disposable Valkey container in Python, connect with valkey-glide, and run basic operations — all torn down automatically when you're done.

**Beginner** · Python · ~5 min

**Who is this for:** Python developers who want to run integration tests against a real Valkey instance without installing Valkey on their machine or sharing a test server with teammates.

## How TestContainers Works

TestContainers manages Docker containers programmatically. The Valkey module provides a
`ValkeyContainer` class that starts a Valkey server, waits for it to accept connections,
and exposes the mapped port. When the context manager exits, the container is stopped and removed.

```text
with ValkeyContainer() as valkey:
    host = valkey.get_host()       # e.g., "localhost"
    port = valkey.get_exposed_port()  # e.g., 55123 (random mapped port)
    # ... run your tests ...
# Container is gone — zero cleanup needed
```

## Prerequisites

- Docker or Podman installed and running
- Python 3.9+

## Step 1: Install Dependencies

```bash
pip install "testcontainers[valkey]==4.15.0" valkey-glide-sync==2.5.0
```

This installs:

- `testcontainers[valkey]` — the container management library with the Valkey module
- `valkey-glide-sync` — the official Valkey client (synchronous API)

## Step 2: Launch a Valkey Container

```python
from testcontainers.community.valkey import ValkeyContainer

with ValkeyContainer() as valkey:
    print(f"Valkey running at {valkey.get_host()}:{valkey.get_exposed_port()}")
    print(f"Connection URL: {valkey.get_connection_url()}")
```

By default, `ValkeyContainer()` uses `valkey/valkey:latest`. Each run gets a random host port, so multiple tests can run in parallel without conflicts.

## Step 3: Connect with valkey-glide

```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress
from testcontainers.community.valkey import ValkeyContainer

with ValkeyContainer() as valkey:
    config = GlideClientConfiguration(
        [NodeAddress(valkey.get_host(), valkey.get_exposed_port())]
    )
    client = GlideClient.create(config)

    # Basic operations
    client.set("greeting", "hello from testcontainers")
    value = client.get("greeting")
    print(f"Got: {value.decode()}")  # "hello from testcontainers"

    client.close()
```

> ⚠️ **Security:** TestContainers instances are ephemeral and local-only — they bind to
> a random port on localhost and are destroyed after the test. No authentication or TLS
> is needed for this use case. For production deployments, always enable authentication
> and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 4: Use the Bundle Image (Search Module)

If your tests need Valkey Search (vector indexes, full-text search), use the bundle image:

```python
from testcontainers.community.valkey import ValkeyContainer

with ValkeyContainer().with_bundle() as valkey:
    # valkey/valkey-bundle:latest — includes the Search module
    print(f"Bundle image: {valkey.image}")
    # Now FT.CREATE, FT.SEARCH, etc. are available
```

## Step 5: Pin a Specific Version

For reproducible CI builds, pin the Valkey version:

```python
from testcontainers.community.valkey import ValkeyContainer

with ValkeyContainer().with_bundle().with_image_tag("9.1.0") as valkey:
    print(f"Using: {valkey.image}")  # valkey/valkey-bundle:9.1.0
```

## How It Works

| Component | Role |
| --------- | ---- |
| `ValkeyContainer()` | Manages the Docker container lifecycle |
| `with_bundle()` | Switches to `valkey/valkey-bundle` image (adds Search module) |
| `with_image_tag("9.1.0")` | Pins a specific Valkey version |
| `with_password("secret")` | Enables `requirepass` authentication |
| `get_host()` | Returns the container's reachable hostname |
| `get_exposed_port()` | Returns the random mapped port on the host |
| `get_connection_url()` | Returns `valkey://host:port` (or with password) |

## Configuration Reference

| Method | Default | Description |
| ------ | ------- | ----------- |
| `ValkeyContainer(image)` | `valkey/valkey:latest` | Base image to use |
| `.with_bundle()` | — | Switch to `valkey/valkey-bundle` |
| `.with_image_tag(tag)` | `latest` | Pin a specific version tag |
| `.with_password(pw)` | None (no auth) | Enable `requirepass` |
| `.get_host()` | — | Container hostname |
| `.get_exposed_port()` | — | Mapped port on host |
| `.get_connection_url()` | — | Full connection URL |

## Cleanup

Nothing to clean up — TestContainers removes the container automatically when the `with` block exits. If a test crashes, TestContainers' Ryuk sidecar container garbage-collects orphaned containers.

---

[← README](README.md) | [02 - Integration Testing →](02-integration-testing.md)
