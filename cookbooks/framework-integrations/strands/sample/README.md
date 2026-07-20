# Strands + Valkey Sample

This sample runs the Strands session-manager flow against Valkey with a local
Ollama model. It demonstrates persistent session, agent, and message records
without external model credentials.

## Prerequisites

- Python 3.11
- Docker or Podman
- A container runtime that can run `valkey/valkey-bundle:9.1.1`
- Enough local disk and memory for the `llama3.2:1b` Ollama model

Strands Agents is an open-source agent SDK maintained by Amazon. The sample
uses the public Strands API and the community
`strands-valkey-session-manager` package. Ollama runs locally in a container,
so no provider account or API key is required.

## Setup and Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
docker compose up -d --wait
docker compose exec -T ollama ollama pull "${OLLAMA_MODEL:-llama3.2:1b}"
.venv/bin/python demo.py
```

Expected output includes:

```text
Persisted messages: 4
Resumed response: [model-generated response]
```

Run the integration tests:

```bash
.venv/bin/python -m pytest -q
```

The tests create a session, run two agent instances for the same session and
agent ID,
inspect the stored messages through `ValkeySessionManager`, and verify that
cleanup removes the session keys.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `localhost` | Valkey server hostname. |
| `VALKEY_PORT` | `6379` | Valkey server port. |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_MODEL` | `llama3.2:1b` | Ollama model tag to pull and use. |

## Teardown

The sample calls `delete_session()` in a `finally` block. Stop the container
and remove its volume after testing:

```bash
docker compose down -v
```
