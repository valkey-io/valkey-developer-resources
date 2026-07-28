# TestContainers Python + Valkey — Sample

Runnable sample code for the TestContainers Python + Valkey cookbook.

## Prerequisites

- Docker or Podman running
- Python 3.9+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

## Run the Demo

```bash
python main.py
```

Expected output:

```text
=== Basic Example ===
Valkey running at localhost:55XXX
Connection URL: valkey://localhost:55XXX
PING: PONG
GET greeting: hello from testcontainers
Counter after 3 increments: 3
Container stopped and removed.

=== Password Example ===
Authenticated Valkey at localhost:55YYY
Connection URL: valkey://:my-secret@localhost:55YYY
PING (authed): PONG
Container stopped and removed.

=== Version Pinning Example ===
Image: valkey/valkey:8.1.1
PING (v8.1.1): PONG
Container stopped and removed.

All examples completed successfully.
```

## Run Tests

```bash
pytest test_valkey_container.py -v
```

Expected: all tests pass. No external Valkey server needed — TestContainers
starts its own Docker containers automatically.

## Teardown

Nothing to clean up. TestContainers removes containers automatically.
If you started a Valkey container with docker-compose for other experiments:

```bash
docker compose down -v
```

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DOCKER_HOST` | (system default) | Docker daemon URL (for remote Docker) |
| `TESTCONTAINERS_RYUK_DISABLED` | `false` | Disable Ryuk cleanup sidecar |
